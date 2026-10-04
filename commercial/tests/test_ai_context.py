import copy
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ai_context', ROOT/'scripts/ai-context.py')
context=importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
def test_manifest():
    assert context.validate(context.load()) == []
def test_transitive_consumers():
    result=context.affected(context.load(), ['commercial/security.py'])
    assert {'identity','access','bpms','meetings','ai','ui','installation'} <= set(result['modules'])
    assert 'commercial/tests/test_secretary_workflow.py' in result['tests']
def test_unknown_or_empty_requires_full_suite():
    for paths in ([], ['new_module/service.py'], ['commercial/security.py','new_module.py']):
        assert context.affected(context.load(), paths)['tests'] == ['commercial/tests']
def test_windows_path_and_test_owner():
    result=context.affected(context.load(), [r'.\commercial\tests\test_license_codec.py'])
    assert {'licensing','ai'} <= set(result['modules']) and not result['unknown']
def test_cycle_and_missing_file():
    modules=copy.deepcopy(context.load())
    modules['identity']['depends_on']=['access']
    modules['identity']['entrypoints'].append('../outside')
    errors=context.validate(modules)
    assert any('cycle' in e for e in errors) and any('unsafe' in e for e in errors)
def test_no_partial_contract_on_budget_overflow(capsys):
    assert context.main(['show','identity','--max-chars','256']) == 2
    captured=capsys.readouterr()
    assert not captured.out and 'budget exceeded' in captured.err
def test_small_card_not_source_dump(capsys):
    assert context.main(['show','identity']) == 0
    text=capsys.readouterr().out
    assert len(text)<2200 and 'def ' not in text
    assert 'Contract:' in text and 'Tests:' in text
