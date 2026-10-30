"""Guard the reviewed Study Abroad migration from accidental destructive DDL.

Offline AST inspection only; never imports Alembic or opens a database.
"""
import ast
from collections import Counter
from pathlib import Path
import unittest

MIGRATION = (
    Path(__file__).resolve().parents[2] / "backend" / "alembic"
    / "versions" / "d4ec2f9b7860_study_abroad_cases.py"
)
EXPECTED_TABLES = {
    "study_cases", "study_case_documents",
    "study_research_reports", "study_universities",
}
EXPECTED_INDEX_TABLES = {
    ("ix_study_cases_owner_updated", "study_cases"),
    ("ix_study_research_reports_case_id", "study_research_reports"),
    ("ix_study_universities_case_id", "study_universities"),
}
EXPECTED_REFERENCES = Counter({
    "users.id": 1, "documents.id": 1, "study_cases.id": 3,
})


def _literal(node):
    return node.value if isinstance(node, ast.Constant) else None


class StudyMigrationAdditiveContractTest(unittest.TestCase):
    def test_revision_chain_and_no_op_execute_alter_or_drop_in_upgrade(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        assignments = {
            target.id: _literal(assignment.value)
            for assignment in tree.body
            if isinstance(assignment, ast.Assign)
            for target in assignment.targets
            if isinstance(target, ast.Name)
        }
        self.assertEqual(assignments.get("revision"), "d4ec2f9b7860")
        self.assertEqual(assignments.get("down_revision"), "b5e4a019dc72")
        upgrades = [
            item for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name == "upgrade"
        ]
        self.assertEqual(len(upgrades), 1)
        upgrade = upgrades[0]
        self.assertEqual(len(upgrade.args.args), 0)

        operations = [
            node for node in ast.walk(upgrade)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
        ]
        self.assertEqual(len(operations), 7)
        self.assertEqual(
            Counter(node.func.attr for node in operations),
            Counter({"create_table": 4, "create_index": 3}),
        )
        actual_tables = set()
        actual_indexes = set()
        for node in operations:
            if node.func.attr == "create_table":
                name = _literal(node.args[0])
                self.assertIsInstance(name, str)
                actual_tables.add(name)
            if node.func.attr == "create_index":
                name = _literal(node.args[0])
                table = _literal(node.args[1])
                self.assertIsInstance(name, str)
                self.assertIsInstance(table, str)
                actual_indexes.add((name, table))
        self.assertEqual(actual_tables, EXPECTED_TABLES)
        self.assertEqual(actual_indexes, EXPECTED_INDEX_TABLES)

    def test_owner_and_document_foreign_keys_retain_cascades(self):
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        upgrades = [
            item for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name == "upgrade"
        ]
        self.assertEqual(len(upgrades), 1)
        fks = [
            node for node in ast.walk(upgrades[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sa"
            and node.func.attr == "ForeignKey"
        ]
        self.assertEqual(
            Counter(_literal(call.args[0]) for call in fks),
            EXPECTED_REFERENCES,
        )
        for call in fks:
            self.assertIn(
                ("ondelete", "CASCADE"),
                [(kw.arg, _literal(kw.value)) for kw in call.keywords],
            )


if __name__ == "__main__":
    unittest.main()
