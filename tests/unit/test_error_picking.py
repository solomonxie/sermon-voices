import unittest
from unittest.mock import patch, MagicMock
from src.process_audio import pick_errors, refine_text

class TestErrorPicking(unittest.TestCase):

    @patch('src.process_audio.ask_llm')
    def test_pick_errors(self, mock_ask):
        # Mock LLM response
        mock_ask.return_value = {
            "errors": [
                "- 语法错误：'还还有' 重复",
                "- 圣经事实：应该是 '彼得' 而不是 '彼得鲁'"
            ]
        }
        
        text = "这就是那个彼得鲁，他还还有很多话。"
        result = pick_errors(text)
        
        self.assertIn("- 语法错误：'还还有' 重复", result)
        self.assertIn("- 圣经事实：应该是 '彼得' 而不是 '彼得鲁'", result)
        mock_ask.assert_called_once()

    @patch('src.process_audio.ask_llm')
    def test_refine_text_with_errors(self, mock_ask):
        # Mock LLM response for refinement
        mock_ask.return_value = {"refined_text": "这就是那个彼得，他还有很多话。"}
        
        text = "这就是那个彼得鲁，他还还有很多话。"
        error_list = "- 圣经事实：应该是 '彼得' 而不是 '彼得鲁'\n- 语法错误：'还还有' 重复"
        
        result = refine_text(text, error_list=error_list)
        
        self.assertEqual(result, "这就是那个彼得，他还有很多话。")
        # Verify that error_list was in the prompt
        args, kwargs = mock_ask.call_args
        prompt = args[0]
        self.assertIn("IDENTIFIED ERRORS TO FIX", prompt)
        self.assertIn(error_list, prompt)

if __name__ == '__main__':
    unittest.main()
