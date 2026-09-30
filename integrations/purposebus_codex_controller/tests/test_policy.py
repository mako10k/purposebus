import unittest

from purposebus_codex_controller import FirstProofPolicy


class FirstProofPolicyTest(unittest.TestCase):
    def test_default_policy_is_the_closed_first_proof_boundary(self) -> None:
        self.assertEqual(
            FirstProofPolicy(),
            FirstProofPolicy(
                filesystem_read_only=True,
                network_access=False,
                max_codex_sessions=1,
                max_subagents=0,
                experimental_app_server_api=False,
            ),
        )

    def test_policy_rejects_every_authority_expansion(self) -> None:
        cases = (
            {"filesystem_read_only": False},
            {"network_access": True},
            {"max_codex_sessions": 2},
            {"max_subagents": 1},
            {"experimental_app_server_api": True},
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                FirstProofPolicy(**values)


if __name__ == "__main__":
    unittest.main()
