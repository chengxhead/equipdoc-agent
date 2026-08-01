import unittest

from scripts.serve_qwen_openai import ChatRequest, validate_server_exposure


class QwenServerSchemaTests(unittest.TestCase):
    def test_openai_chat_payload_is_parsed_as_request_body_model(self):
        request = ChatRequest.model_validate(
            {
                "model": "qwen-equipdoc",
                "messages": [{"role": "user", "content": "只回复 READY"}],
                "temperature": 0.0,
                "max_tokens": 8,
            }
        )
        self.assertEqual(request.model, "qwen-equipdoc")
        self.assertEqual(request.messages[0].content, "只回复 READY")
        self.assertEqual(request.max_tokens, 8)

    def test_remote_binding_requires_authentication_or_explicit_override(self):
        validate_server_exposure("127.0.0.1", "EMPTY")
        validate_server_exposure("0.0.0.0", "secret")
        validate_server_exposure(
            "0.0.0.0",
            "EMPTY",
            allow_unauthenticated_remote=True,
        )
        with self.assertRaisesRegex(ValueError, "unauthenticated"):
            validate_server_exposure("0.0.0.0", "EMPTY")


if __name__ == "__main__":
    unittest.main()
