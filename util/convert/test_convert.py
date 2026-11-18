"""Unit tests for the notebook -> tutorial markdown converter.

Run from anywhere: python -m unittest discover -s util/convert
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import convert

SCRIPT = os.path.abspath(convert.__file__)


def write_notebook(path, source="print('hi')"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "id": "md-1",
                "metadata": {},
                "source": "# Title",
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "code-1",
                "metadata": {},
                "outputs": [],
                "source": source,
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f)


class OutputNameTest(unittest.TestCase):
    def test_nested_path_is_flattened_with_hyphens(self):
        self.assertEqual(
            convert.output_name(os.path.join("google_adk", "Tutorial.ipynb")),
            "google_adk-Tutorial.md",
        )

    def test_top_level_notebook_keeps_its_name(self):
        self.assertEqual(convert.output_name("Tutorial.ipynb"), "Tutorial.md")


class ConvertNotebookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.exporter = convert.build_exporter()

    def tearDown(self):
        self.tmp.cleanup()

    def test_notebook_without_frontmatter_is_skipped(self):
        nb = os.path.join(self.root, "demo", "Demo.ipynb")
        write_notebook(nb)
        self.assertIsNone(convert.convert_notebook(nb, self.exporter, self.root))

    def test_frontmatter_warning_and_source_link_prefix_body(self):
        nb = os.path.join(self.root, "demo", "Demo.ipynb")
        write_notebook(nb)
        with open(os.path.join(self.root, "demo", "frontmatter.md"), "w") as f:
            f.write("---\ntitle: Demo\n---")

        name, markdown = convert.convert_notebook(nb, self.exporter, self.root)

        self.assertEqual(name, "demo-Demo.md")
        self.assertTrue(
            markdown.startswith("---\ntitle: Demo\n---\n\n<!--- *** WARNING")
        )
        self.assertIn(
            f"[View Source]({convert.base_github_url}/demo/Demo.ipynb)", markdown
        )
        self.assertIn("# Title", markdown)


class WorkingDirectoryIndependenceTest(unittest.TestCase):
    def test_paths_are_anchored_to_the_script_not_the_cwd(self):
        script_dir = os.path.dirname(SCRIPT)
        self.assertEqual(convert.markdown_dir, os.path.join(script_dir, "output_md"))
        self.assertEqual(
            convert.project_dir, os.path.normpath(os.path.join(script_dir, "..", ".."))
        )

    def test_import_from_another_cwd_resolves_same_paths(self):
        with tempfile.TemporaryDirectory() as other_cwd:
            out = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); import convert;"
                    " print(convert.project_dir); print(convert.markdown_dir)",
                    os.path.dirname(SCRIPT),
                ],
                cwd=other_cwd,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
        self.assertEqual(out, [convert.project_dir, convert.markdown_dir])


if __name__ == "__main__":
    unittest.main()
