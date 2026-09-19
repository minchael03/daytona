import os
import unittest

from playwright.sync_api import sync_playwright

import rules

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "rules")


def fixture_url(name):
    path = os.path.join(FIXTURES_DIR, name)
    return "file://" + os.path.abspath(path)


def find_finding(findings, rule_id, target):
    for finding in findings:
        if finding["rule_id"] == rule_id and finding["target"] == target:
            return finding
    return None


class ContrastPureFunctionTests(unittest.TestCase):
    def test_black_on_white_is_21_to_1(self):
        self.assertAlmostEqual(rules.contrast_ratio((0, 0, 0), (255, 255, 255)), 21)

    def test_identical_colors_is_1_to_1(self):
        self.assertAlmostEqual(rules.contrast_ratio((90, 90, 90), (90, 90, 90)), 1)

    def test_large_text_requires_3_to_1(self):
        self.assertEqual(rules.required_contrast(24, 400), 3)

    def test_normal_text_requires_4_5_to_1(self):
        self.assertEqual(rules.required_contrast(16, 400), 4.5)

    def test_bold_18_667px_counts_as_large(self):
        self.assertEqual(rules.required_contrast(18.667, 700), 3)

    def test_below_boundary_fails(self):
        self.assertFalse(rules.meets_contrast(4.499, 4.5))

    def test_at_boundary_passes(self):
        self.assertTrue(rules.meets_contrast(4.5, 4.5))


class DomFixtureTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()

    def tearDown(self):
        self.page.close()

    def scan_fixture(self, name):
        self.page.goto(fixture_url(name))
        return rules.scan(self.page)


class ImageAltRuleTests(DomFixtureTestCase):
    def test_missing_alt_and_no_name_is_fail(self):
        result = self.scan_fixture("image_alt.html")
        finding = find_finding(result["findings"], "image_alt", "#img-missing")
        self.assertEqual(finding["status"], "fail")

    def test_empty_alt_needs_review(self):
        result = self.scan_fixture("image_alt.html")
        finding = find_finding(result["findings"], "image_alt", "#img-empty-alt")
        self.assertEqual(finding["status"], "needs_review")

    def test_aria_label_passes(self):
        result = self.scan_fixture("image_alt.html")
        finding = find_finding(result["findings"], "image_alt", "#img-aria-label")
        self.assertEqual(finding["status"], "pass")

    def test_title_only_needs_review(self):
        result = self.scan_fixture("image_alt.html")
        finding = find_finding(result["findings"], "image_alt", "#img-title-only")
        self.assertEqual(finding["status"], "needs_review")

    def test_good_alt_passes(self):
        result = self.scan_fixture("image_alt.html")
        finding = find_finding(result["findings"], "image_alt", "#img-good-alt")
        self.assertEqual(finding["status"], "pass")


class FormLabelRuleTests(DomFixtureTestCase):
    def test_connected_label_passes(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#in-labeled")
        self.assertEqual(finding["status"], "pass")

    def test_placeholder_only_fails(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#in-placeholder-only")
        self.assertEqual(finding["status"], "fail")

    def test_aria_label_passes(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#in-aria-label")
        self.assertEqual(finding["status"], "pass")

    def test_no_name_fails(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#in-no-name")
        self.assertEqual(finding["status"], "fail")

    def test_aria_labelledby_passes(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#ta-labelledby")
        self.assertEqual(finding["status"], "pass")

    def test_hidden_input_excluded(self):
        result = self.scan_fixture("form_label.html")
        finding = find_finding(result["findings"], "form_label", "#in-hidden")
        self.assertIsNone(finding)


class ButtonNameRuleTests(DomFixtureTestCase):
    def test_text_button_passes(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-text")
        self.assertEqual(finding["status"], "pass")

    def test_empty_button_fails(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-empty")
        self.assertEqual(finding["status"], "fail")

    def test_image_alt_button_passes(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-img-alt")
        self.assertEqual(finding["status"], "pass")

    def test_aria_label_button_passes(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-aria-label")
        self.assertEqual(finding["status"], "pass")

    def test_title_only_button_passes(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-title")
        self.assertEqual(finding["status"], "pass")

    def test_input_value_button_passes(self):
        result = self.scan_fixture("button_name.html")
        finding = find_finding(result["findings"], "button_name", "#btn-input-value")
        self.assertEqual(finding["status"], "pass")


class FontSizeRuleTests(DomFixtureTestCase):
    def test_small_font_needs_review(self):
        result = self.scan_fixture("font_size.html")
        finding = find_finding(result["findings"], "font_size", "#f-small")
        self.assertEqual(finding["status"], "needs_review")
        self.assertEqual(finding["basis"], "product-guidance")

    def test_16px_has_no_font_size_finding(self):
        result = self.scan_fixture("font_size.html")
        finding = find_finding(result["findings"], "font_size", "#f-ok")
        self.assertIsNone(finding)

    def test_large_font_has_no_font_size_finding(self):
        result = self.scan_fixture("font_size.html")
        finding = find_finding(result["findings"], "font_size", "#f-large")
        self.assertIsNone(finding)


class ContrastDomRuleTests(DomFixtureTestCase):
    def test_black_on_white_passes(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-pass-normal")
        self.assertEqual(finding["status"], "pass")

    def test_identical_colors_fail(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-fail-same")
        self.assertEqual(finding["status"], "fail")

    def test_normal_size_below_4_5_fails(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-fail-normal-boundary")
        self.assertEqual(finding["status"], "fail")

    def test_large_size_same_ratio_passes(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-pass-large-boundary")
        self.assertEqual(finding["status"], "pass")

    def test_bold_large_size_same_ratio_passes(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-pass-bold-large")
        self.assertEqual(finding["status"], "pass")

    def test_gradient_background_needs_review(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-review-gradient")
        self.assertEqual(finding["status"], "needs_review")

    def test_transparent_ancestor_chain_needs_review(self):
        result = self.scan_fixture("contrast.html")
        finding = find_finding(result["findings"], "contrast", "#c-review-transparent")
        self.assertEqual(finding["status"], "needs_review")


class ScanContractTests(DomFixtureTestCase):
    def test_scan_returns_snapshot_and_findings_without_mutating_dom(self):
        self.page.goto(fixture_url("image_alt.html"))
        before = self.page.content()
        result = rules.scan(self.page)
        after = self.page.content()
        self.assertIn("snapshot", result)
        self.assertIn("findings", result)
        self.assertEqual(before, after)

    def test_inspect_snapshot_is_pure_and_json_serializable(self):
        import json

        self.page.goto(fixture_url("image_alt.html"))
        snapshot = self.page.evaluate(rules._COLLECT_JS)
        findings_first = rules.inspect_snapshot(snapshot)
        findings_second = rules.inspect_snapshot(snapshot)
        self.assertEqual(findings_first, findings_second)
        json.dumps(findings_first)


if __name__ == "__main__":
    unittest.main()
