"""Celery GPU worker: trains a phenotype, profiles latency, checkpoints to MinIO, exports ONNX.
For Ray: wrap run_trial_impl in @ray.remote(num_gpus=1) and dispatch from the orchestrator instead."""
from __future__ import annotations
import io, os, socket, threading, time, uuid
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_ready, worker_shutdown
from minio import Minio
import redis, json
import torch, torch.nn as nn, torchvision, torchvision.transforms as T
from app.config import settings
from app.nas.genotype import Genotype, build_model, count_params

celery = Celery("deepoptima", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_acks_late=True, worker_prefetch_multiplier=1, task_reject_on_worker_lost=True,
                   task_routes={"app.workers.tasks.run_trial": {"queue": "gpu"}})
if settings.mtls_enabled:
    celery.conf.broker_use_ssl = settings.celery_ssl(); celery.conf.redis_backend_use_ssl = settings.celery_ssl()
_r = redis.Redis.from_url(settings.redis_url, **settings.redis_kwargs())
_s3 = Minio(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key, secure=False)


_stop = threading.Event()

def _beat():
    """Register this node in Redis every 15s (TTL 45s): the API lists live workers from these keys."""
    host = socket.gethostname()
    cuda = torch.cuda.is_available()
    info = {"gpu": torch.cuda.get_device_name(0) if cuda else "cpu",
            "gpu_mem_mb": int(torch.cuda.get_device_properties(0).total_memory / 1e6) if cuda else 0,
            "torch": torch.__version__, "queue": "gpu"}
    while not _stop.is_set():
        try:
            _r.hset(f"worker:{host}", mapping={**info, "last_heartbeat": int(time.time())}); _r.expire(f"worker:{host}", 45)
        except Exception:
            pass
        _stop.wait(15)

@worker_ready.connect
def _on_ready(**_):
    threading.Thread(target=_beat, daemon=True).start()

@worker_shutdown.connect
def _on_shutdown(**_):
    _stop.set()
    try: _r.delete(f"worker:{socket.gethostname()}")
    except Exception: pass

def _publish(exp_id: str, trial_id: str, event: dict):
    _r.publish(f"exp:{exp_id}", json.dumps({"trial_id": trial_id, **event}))


def _loaders(batch_size: int, subset: int = 10_000):
    tf = T.Compose([T.ToTensor(), T.Normalize((0.49, 0.48, 0.45), (0.25, 0.24, 0.26))])
    root = os.environ.get("DATA_DIR", "/data")
    tr = torchvision.datasets.CIFAR10(root, True, transform=tf, download=True)
    te = torchvision.datasets.CIFAR10(root, False, transform=tf, download=True)
    tr = torch.utils.data.Subset(tr, range(subset)); te = torch.utils.data.Subset(te, range(2000))
    mk = lambda d, sh: torch.utils.data.DataLoader(d, batch_size=batch_size, shuffle=sh, num_workers=2)
    return mk(tr, True), mk(te, False)


def _latency_ms(model, dev, runs=20) -> float:
    model.eval(); x = torch.randn(1, 3, 32, 32, device=dev)
    with torch.no_grad():
        for _ in range(5): model(x)
        if dev.type == "cuda": torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(runs): model(x)
        if dev.type == "cuda": torch.cuda.synchronize()
    return (time.perf_counter() - t) / runs * 1000


def _put(key: str, buf: io.BytesIO):
    if not _s3.bucket_exists(settings.minio_bucket): _s3.make_bucket(settings.minio_bucket)
    buf.seek(0); _s3.put_object(settings.minio_bucket, key, buf, len(buf.getvalue()))


def _get(key: str):
    try:
        return io.BytesIO(_s3.get_object(settings.minio_bucket, key).read())
    except Exception:
        return None


@celery.task(bind=True, name="app.workers.tasks.run_trial", max_retries=2,
             soft_time_limit=settings.trial_timeout_s, time_limit=settings.trial_timeout_s + 60)
def run_trial(self, experiment_id: str, trial_id: str, genotype: dict, epochs: int = 3,
              export_onnx: bool = False) -> dict:
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    g = Genotype.from_dict(genotype)
    model = build_model(g).to(dev)
    opt = (torch.optim.AdamW(model.parameters(), g.lr, weight_decay=g.weight_decay) if g.optimizer == "adamw"
           else torch.optim.SGD(model.parameters(), g.lr, momentum=0.9, weight_decay=g.weight_decay))
    ckpt_key = f"{experiment_id}/{trial_id}/last.pt"
    start_epoch, curve = 0, []
    ck = _get(ckpt_key)                                  # automatic checkpoint recovery
    if ck:
        st = torch.load(ck, map_location=dev)
        model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"])
        start_epoch, curve = st["epoch"], st["curve"]
    tr, te = _loaders(g.batch_size)
    lossf = nn.CrossEntropyLoss()
    _publish(experiment_id, trial_id, {"event": "started", "host": socket.gethostname()})
    try:
        for ep in range(start_epoch, epochs):
            model.train(); tot = n = 0
            for x, y in tr:
                x, y = x.to(dev), y.to(dev)
                opt.zero_grad(); loss = lossf(model(x), y)
                if not torch.isfinite(loss): raise FloatingPointError("loss diverged (NaN/Inf)")
                loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step()
                tot += loss.item() * len(x); n += len(x)
            curve.append(tot / n)
            _publish(experiment_id, trial_id, {"event": "epoch", "epoch": ep + 1, "loss": curve[-1]})
            buf = io.BytesIO(); torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                                            "epoch": ep + 1, "curve": curve}, buf); _put(ckpt_key, buf)
        model.eval(); correct = total = 0
        with torch.no_grad():
            for x, y in te:
                correct += (model(x.to(dev)).argmax(1).cpu() == y).sum().item(); total += len(y)
        result = {"status": "completed", "accuracy": correct / total, "latency_ms": _latency_ms(model, dev),
                  "params": count_params(model), "loss_curve": curve, "checkpoint_key": ckpt_key}
        if export_onnx:
            buf = io.BytesIO(); model.cpu().eval()
            torch.onnx.export(model, torch.randn(1, 3, 32, 32), buf, opset_version=17,
                              input_names=["input"], output_names=["logits"], dynamic_axes={"input": {0: "b"}})
            key = f"{experiment_id}/{trial_id}/model.onnx"; _put(key, buf); result["onnx_key"] = key
        _publish(experiment_id, trial_id, {"event": "done", **{k: result[k] for k in ("accuracy", "latency_ms", "params")}})
        return result
    except SoftTimeLimitExceeded:
        _publish(experiment_id, trial_id, {"event": "timeout"})
        return {"status": "timeout", "loss_curve": curve, "error": "trial timeout"}
    except (FloatingPointError, RuntimeError, ValueError) as e:   # deterministic failures: do not retry, route to agent swarm
        _publish(experiment_id, trial_id, {"event": "failed", "error": str(e)})
        return {"status": "failed", "error": str(e), "loss_curve": curve}
