"""Read-only, hash-checked loader for the frozen PPT875 reference implementation."""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from threading import RLock
from types import SimpleNamespace

SNAPSHOT = Path(__file__).resolve().parents[1] / 'baselines' / 'ppt875_20260924'
_LOCK = RLock()


def normalized_text(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').rstrip('\n') + '\n'


def verify_snapshot(directory=SNAPSHOT):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8-sig'))
    for name, expected in manifest['normalized_sha256'].items():
        if Path(name).name != name:
            raise ValueError('snapshot manifest must contain local filenames only')
        text = (directory / name).read_text(encoding='utf-8-sig')
        actual = hashlib.sha256(normalized_text(text).encode('utf-8')).hexdigest()
        if actual != expected:
            raise ValueError(f'frozen baseline changed: {name}')
    return manifest


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SNAPSHOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_baseline():
    # Frozen files retain their original imports. Restore aliases immediately;
    # importing this loader never runs the original scripts' writing entrypoints.
    with _LOCK:
        manifest = verify_snapshot()
        names = ('safety_evaluation', 'failure_response_barrier_model')
        sentinel = object()
        previous = {name: sys.modules.get(name, sentinel) for name in names}
        try:
            safety = _module('_ppt875_safety', 'safety_evaluation.py')
            sys.modules[names[0]] = safety
            model = _module('_ppt875_model', 'failure_response_barrier_model.py')
            sys.modules[names[1]] = model
            generator = _module('_ppt875_generator', 'synthetic_dataset_evaluation.py')
        finally:
            for name, old in previous.items():
                if old is sentinel:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old
        return SimpleNamespace(safety=safety, model=model, generator=generator,
                               manifest=manifest)
