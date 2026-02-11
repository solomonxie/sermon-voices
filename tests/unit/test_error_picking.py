import unittest
from unittest.mock import patch, MagicMock
from src.process_audio import pick_zh_errors, refine_text

class TestErrorPicking(unittest.TestCase):

    @patch('src.process_audio.ask_openai')
    def test_pick_zh_errors_list_of_strings(self, mock_ask):
        # Mock LLM response with list of strings
        mock_ask.return_value = {
            "errors": [
                "- 语法错误：'还还有' 重复",
                "- 圣经事实：应该是 '彼得' 而不是 '彼得鲁'"
            ]
        }
        
        text = "这就是那个彼得鲁，他还还有很多话。"
        result = pick_zh_errors(text)
        
        self.assertIn("- 语法错误：'还还有' 重复", result)
        self.assertIn("- 圣经事实：应该是 '彼得' 而不是 '彼得鲁'", result)
        mock_ask.assert_called_once()

    @patch('src.process_audio.ask_openai')
    def test_pick_zh_errors_list_of_dicts(self, mock_ask):
        # Mock LLM response with list of dicts (the bug case)
        mock_ask.return_value = {
            "errors": [
                {"issue": "重复词", "suggestion": "'还还有' -> '还有'"},
                {"issue": "圣经名词错误", "suggestion": "'彼得鲁' -> '彼得'"}
            ]
        }
        
        text = "这就是那个彼得鲁，他还还有很多话。"
        result = pick_zh_errors(text)
        
        self.assertIn("重复词: '还还有' -> '还有'", result)
        self.assertIn("圣经名词错误: '彼得鲁' -> '彼得'", result)

    @patch('src.process_audio.ask_openai')
    def test_pick_zh_errors_string(self, mock_ask):
        # Mock LLM response with a simple string
        mock_ask.return_value = {
            "errors": "- 语法错误\n- 圣经名词错误"
        }
        
        result = pick_zh_errors("some text")
        self.assertEqual(result, "- 语法错误\n- 圣经名词错误")

    @patch('src.process_audio.ask_openai')
    def test_refine_text_with_context(self, mock_ask):
        # Mock LLM response for refinement
        mock_ask.return_value = {"refined_text": "这就是那个彼得，他还有很多话。"}
        
        text = "这就是那个彼得鲁，他还还有很多话。"
        extra_context = "--- START IDENTIFIED ERRORS ---\n- 圣经事实: 彼得\n--- END IDENTIFIED ERRORS ---"
        
        result = refine_text(text, extra_context=extra_context)
        
        self.assertEqual(result, "这就是那个彼得，他还有很多话。")
        # Verify that extra_context was in the prompt
        args, kwargs = mock_ask.call_args
        prompt = args[0]
        self.assertIn(extra_context, prompt)

if __name__ == '__main__':
    unittest.main()
