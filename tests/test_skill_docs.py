"""Keep the method layer generic and the documentation trustworthy.

Site names, SDK names and site parameters belong in cases/. Keywords are read
from the case index, so a new case automatically protects the core documents.
A private, git-ignored term list can add names that must never be published.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = [ROOT / 'SKILL.md', ROOT / 'README.md', *sorted((ROOT / 'references').glob('*.md')),
        *sorted((ROOT / 'templates/param-tracking').glob('*.md'))]
PUBLISHED = CORE + sorted((ROOT / 'cases').glob('*.md')) + sorted((ROOT / 'docs').rglob('*.md')) \
    + sorted((ROOT / 'evals').rglob('*.md')) + sorted((ROOT / 'evals').rglob('*.yaml'))
PRIVATE_TERMS = ROOT / 'tests/private_terms.local.txt'
# Terms in the case index that are also generic technology words.
GENERIC_KEYWORDS = {'obfuscator.io', '_0x', '412', 'while-switch', '200KB+', '200KB', 'switch', 'sign',
                    'token'}
# Vendor names that the index mentions in prose rather than as backticked keywords.
EXTRA_SITE_TERMS = ['tiktok', 'douyin', '抖音', '瑞数', 'akamai', 'cloudflare', '极验', 'geetest', 'bdms', 'ttwid']
# Removed tools may only be named in the migration table and the old-rule index.
TOOL_ALLOWED = {'mcp-tool-reference.md', 'mcp-tools.json', 'experience-rules-full.md'}
STALE_TOOLS = ['add_init_script', 'bypass_debugger_trap', 'dump_jsvmp_strings', 'get_runtime_probe_log',
               'reload_with_hooks', 'get_fingerprint_info', 'check_detection', 'get_instrumentation_log',
               'instrument_jsvmp_source', 'get_cookies', 'get_script_source', 'set_breakpoint_via_hook',
               'start_network_capture', 'get_breakpoint_data', 'find_dispatch_loops', 'via_blank']
OVERCLAIMS = ['终极壁垒', '第一杀手', '只有一条路', '唯一能', '必须走', '永远不要', '快 10 倍', '70%+', '最可靠',
              '严禁尝试反编译']


def read(path):
    return path.read_text(encoding='utf-8')


def code_free(text):
    return re.sub(r'```.*?```', '', text, flags=re.S)


def prose_only(text):
    return re.sub(r'`[^`\n]*`', '', code_free(text))


def slug(heading):
    text = re.sub(r'`', '', heading.strip().lower())
    text = re.sub(r'[^\w\- ]', '', text, flags=re.U)
    return text.replace(' ', '-')


def anchors(path):
    return {slug(match.group(1)) for match in re.finditer(r'^#{1,6}\s+(.+)$', code_free(read(path)), re.M)}


def case_keywords():
    table = read(ROOT / 'cases/README.md').split('## 案例索引')[0]
    found = set()
    for line in table.splitlines():
        if line.startswith('|'):
            first_cell = line.split('|')[1]
            found.update(re.findall(r'`([^`]+)`', first_cell))
    return {item for item in found if item not in GENERIC_KEYWORDS and len(item) >= 4}


class GenericMethodTests(unittest.TestCase):
    def assert_absent(self, terms, files, message):
        hits = []
        for path in files:
            lowered = read(path).lower()
            hits += [f'{path.relative_to(ROOT)}: {term}' for term in terms if term.lower() in lowered]
        self.assertFalse(hits, f'{message}\n' + '\n'.join(hits))

    def test_case_index_yields_keywords(self):
        self.assertGreater(len(case_keywords()), 5)

    def test_core_documents_do_not_name_sites_or_site_parameters(self):
        allowed = {ROOT / 'references/experience-rules-full.md'}
        files = [path for path in CORE if path not in allowed]
        self.assert_absent(sorted(case_keywords()) + EXTRA_SITE_TERMS, files,
                           'Site-specific names belong in cases/, not in the method layer:')

    def test_private_terms_never_reach_published_files(self):
        if not PRIVATE_TERMS.exists():
            self.skipTest('no local private term list')
        terms = [line.strip() for line in read(PRIVATE_TERMS).splitlines() if line.strip() and not line.startswith('#')]
        self.assert_absent(terms, PUBLISHED, 'Private terms must not be published:')

    def test_core_documents_avoid_overclaims(self):
        files = [path for path in CORE if path.name != 'experience-rules-full.md']
        self.assert_absent(OVERCLAIMS, files, 'Absolute claims go stale; write a scoped observation instead:')


class ToolAccuracyTests(unittest.TestCase):
    def test_removed_tools_are_not_presented_as_callable(self):
        hits = []
        for path in CORE + [ROOT / 'examples/demo-analysis.md']:
            if path.name in TOOL_ALLOWED:
                continue
            text = read(path)
            hits += [f'{path.relative_to(ROOT)}: {name}' for name in STALE_TOOLS if name in text]
        self.assertFalse(hits, '\n'.join(hits))

    def test_unregistered_cookie_analysis_is_only_named_as_unavailable(self):
        for path in CORE:
            if path.name in TOOL_ALLOWED:
                continue
            for line in read(path).splitlines():
                if 'analyze_cookie_sources' in line:
                    self.assertIn('未注册', line, f'{path.name}: {line}')

    def test_pre_inject_cookie_uses_the_registered_name(self):
        for path in CORE:
            self.assertNotRegex(read(path), r'pre_inject_hooks=\[[^\]]*"cookie"', path.name)

    def test_contract_snapshot_lists_tools_named_in_skill(self):
        tools = {item['name'] for item in json.loads(read(ROOT / 'references/mcp-tools.json'))['tools']}
        for name in ('check_environment', 'network_capture', 'compare_network_requests', 'verify_signer_offline'):
            self.assertIn(name, tools)


class LinkTests(unittest.TestCase):
    def test_relative_links_and_anchors_resolve(self):
        broken = []
        files = CORE + sorted((ROOT / 'cases').glob('*.md')) + sorted((ROOT / 'docs/research').glob('*.md'))
        for path in files:
            for target, anchor in re.findall(r'\]\(([^)#\s]*)(#[^)\s]*)?\)', prose_only(read(path))):
                if target.startswith(('http://', 'https://', 'mailto:')):
                    continue
                resolved = (path.parent / target).resolve() if target else path
                if not resolved.exists():
                    broken.append(f'{path.relative_to(ROOT)} -> {target}')
                elif anchor and resolved.suffix == '.md' and anchor[1:] not in anchors(resolved):
                    broken.append(f'{path.relative_to(ROOT)} -> {target}{anchor}')
        self.assertFalse(broken, '\n'.join(broken))

    def test_skill_links_every_method_reference(self):
        skill = read(ROOT / 'SKILL.md')
        for name in ('problem-routing', 'controlled-experiments', 'signature-source-isolation',
                     'original-sdk-runtime', 'opaque-token-analysis', 'version-tracking',
                     'browser-evidence-contract'):
            self.assertIn(f'references/{name}.md', skill)


class SkillShapeTests(unittest.TestCase):
    def test_body_stays_small_enough_to_load_every_time(self):
        self.assertLess(len(read(ROOT / 'SKILL.md').splitlines()), 220)

    def test_description_stays_within_loader_limits(self):
        match = re.search(r'^description: >\n(.*?)^metadata:', read(ROOT / 'SKILL.md'), re.M | re.S)
        self.assertIsNotNone(match)
        self.assertLessEqual(len(' '.join(match.group(1).split())), 1024)

    def test_version_is_consistent_across_entry_points(self):
        version = re.search(r'^\s*version:\s*"([^"]+)"', read(ROOT / 'SKILL.md'), re.M).group(1)
        self.assertTrue((ROOT / f'docs/releases/v{version}.md').exists())
        self.assertIn(f'v{version}', read(ROOT / 'README.md'))
        self.assertIn(f'v{version}', read(ROOT / 'SKILL.md').split('## 更新记录')[1])


if __name__ == '__main__':
    unittest.main()
