from pathlib import Path
import argparse, importlib.util, runpy, sys, traceback

p = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser(description='Run GemPy model after recording, but not resolving, known data issues.')
    ap.add_argument('--strict', action='store_true', help='fail when known preflight issues exist')
    args = ap.parse_args()
    required = ['gempy', 'gempy_viewer', 'gempy_engine', 'numpy', 'pandas', 'matplotlib']
    missing = [m for m in required if importlib.util.find_spec(m) is None]
    log = [f'python={sys.executable}', f'data_dir={p}']
    if missing:
        log.append('missing=' + ','.join(missing))
        log.append('status=NOT_RUN')
        (p/'gempy_run_status_20261007.log').write_text('\n'.join(log), encoding='utf-8')
        print('GemPy environment incomplete; model not run:', ', '.join(missing))
        return 2
    try:
        runpy.run_path(str(p/'gempy_build_and_section_fixed.py'), run_name='__main__')
        log.append('status=COMPLETED')
        return 0
    except Exception:
        log.append('status=FAILED')
        log.append(traceback.format_exc())
        (p/'gempy_run_status_20261007.log').write_text('\n'.join(log), encoding='utf-8')
        raise

if __name__ == '__main__':
    raise SystemExit(main())
