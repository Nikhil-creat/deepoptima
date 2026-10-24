"""Run user-submitted fitness functions (compiled to Wasm) with fuel + memory limits, no WASI, no host imports.
Contract: exported `fitness(acc: f64, latency_ms: f64, params: f64) -> f64`."""

def validate_module(wasm_bytes: bytes) -> None:
    from wasmtime import Config, Engine, Module
    if len(wasm_bytes) > 1_000_000: raise ValueError("module larger than 1 MB")
    module = Module(Engine(Config()), wasm_bytes)
    if list(module.imports): raise ValueError("imports are not allowed")
    if "fitness" not in [e.name for e in module.exports]: raise ValueError("missing exported function 'fitness'")

def run_fitness(wasm_bytes: bytes, acc: float, latency_ms: float, params: float, fuel: int = 5_000_000) -> float:
    from wasmtime import Config, Engine, Instance, Module, Store, Trap
    cfg = Config(); cfg.consume_fuel = True
    engine = Engine(cfg); store = Store(engine)
    store.set_fuel(fuel)
    store.set_limits(memory_size=64 * 1024 * 1024)
    module = Module(engine, wasm_bytes)
    if list(module.imports):
        raise ValueError("Imports are not allowed in fitness modules")
    inst = Instance(store, module, [])
    try:
        return float(inst.exports(store)["fitness"](store, acc, latency_ms, params))
    except Trap as e:
        raise RuntimeError(f"fitness trapped (fuel/limits): {e}")
