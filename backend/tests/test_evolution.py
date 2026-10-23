import random
from app.nas.genotype import random_genotype, build_model
from app.nas.evolution import nsga2_select, dominates, next_generation

def test_phenotype_forward():
    import torch
    for _ in range(5):
        assert build_model(random_genotype())(torch.randn(2, 3, 32, 32)).shape == (2, 10)

def test_dominates():
    assert dominates((0.1, 1, 1), (0.2, 2, 2)) and not dominates((0.1, 3, 1), (0.2, 2, 2))

def test_nsga_and_offspring():
    pop = [{"genotype": random_genotype().to_dict(), "accuracy": random.random(),
            "latency_ms": random.random() * 10, "params": random.randint(10_000, 1_000_000)} for _ in range(20)]
    elite, ranks = nsga2_select(pop, 10)
    assert len(elite) == 10 and min(ranks) == 0
    assert len(next_generation(elite, 8)) == 8
