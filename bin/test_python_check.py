import unittest
import python_check
import unittest.mock as mock


class TestLessonRunner(unittest.TestCase):
    def test_returns_list(self):
        def yield_good_elements(_):
            yield 'some code', 'some output', 'some error'

        def yield_wrong_error(_):
            yield 'some code', 'some output', 'wrong error'

        def yield_wrong_output(_):
            yield 'some code', 'wrong output', 'some error'

        def run_some_code(_, **kwargs):
            del kwargs
            return 'some output', 'some error'

        self.assertDictEqual({'code_block': 1},
                             python_check.run_episode((), yield_good_elements, run_some_code)[0])
        self.assertDictEqual({'code_block': 1, 'code': 'some code', 'expected_error': 'wrong error', 'actual_error': 'some error'},
                             python_check.run_episode((), yield_wrong_error, run_some_code)[0])
        self.assertDictEqual({'code_block': 1, 'code': 'some code', 'expected_output': 'wrong output', 'actual_output': 'some output'},
                             python_check.run_episode((), yield_wrong_output, run_some_code)[0])


class TestCodeGenerator(unittest.TestCase):
    code1 = {'attr': {'class': 'language-python'},
             'children': [{'type': 'text',
                           'value': 'Any Python interpreter can be used as '
                                    'a calculator:\n~~~\n3 + 5 * 4\n~~~'}]}

    output1 = {'type': 'codeblock',
               'attr': {'class': 'output'},
               'value': '23\n'}

    error1 = {'type': 'codeblock',
              'attr': {'class': 'error'},
              'value': '-' * 75 + '\nIndexError                              '
                                  '  Traceback (most recent call last)\n'
                                  '<ipython-input-3-7974b6cdaf14> in '
                                  '<module>()\n      3 print(word[1])\n     '
                                  ' 4 print(word[2])\n----> 5 print(word[3])\n'
                                  '\nIndexError: string index out of range\n',
              'options': {'location': 73, 'ial': {'class': 'error'}}}

    code2 = {'attr': {'class': 'language-python'},
             'children': [{'type': 'text',
                           'value': '~~~\n'},
                          {'type': 'text',
                           'value': 'lsquo'},
                          {'type': 'text',
                           'value': 'A'},
                          {'type': 'text',
                           'value': 'rsquo'},
                          {'type': 'text',
                           'value': ' * 3\n~~~'}
                          ]}

    output2 = {'type': 'codeblock',
               'attr': {'class': 'output'},
               'value': '\'AAA\'\n'}

    error2 = {'type': 'codeblock',
              'attr': {'class': 'error'},
              'value': '-' * 75 + '\nTypeError'}

    code3 = {'attr': {'class': 'language-python'},
             'children': [{'type': 'text',
                           'value': '~~~\n4 * 3'}]}

    code4 = {'attr': {'class': 'language-python'},
             'value': 'None\n'}

    def test_generator_handles_list(self):
        document_iterator = python_check.get_code_output_and_error([self.code1, self.output1,
                                                                    self.code2, self.output2, self.error2,
                                                                    self.code4])
        a, b, c = next(document_iterator)
        self.assertEqual('3 + 5 * 4', a)
        self.assertEqual('23', b)
        self.assertIsNone(c)

        a, b, c = next(document_iterator)
        self.assertEqual('\'A\' * 3', a)
        self.assertEqual("'AAA'", b)
        self.assertEqual('TypeError', c)

        a, b, c = next(document_iterator)
        self.assertEqual('None', a)
        self.assertIsNone(b)
        self.assertIsNone(c)

    def test_raises_errors(self):
        document_iterator = python_check.get_code_output_and_error((self.output1,))
        self.assertRaises(python_check.BadFormatError, lambda: next(document_iterator))

        document_iterator = python_check.get_code_output_and_error((self.code1, self.output1, self.output1))
        self.assertRaises(python_check.BadFormatError, lambda: next(document_iterator))

        document_iterator = python_check.get_code_output_and_error((self.code3,))
        self.assertRaises(python_check.BadFormatError, lambda: next(document_iterator))

        document_iterator = python_check.get_code_output_and_error((self.error1,))
        self.assertRaises(python_check.BadFormatError, lambda: next(document_iterator))


class TestCodeExecutor(unittest.TestCase):
    def test_expression(self):
        self.assertTupleEqual(('23', None), python_check.run_code_block('3 + 5 * 4'))
        self.assertTupleEqual(("'t'", None), python_check.run_code_block('"t"'))

    def test_none_pass(self):
        self.assertTupleEqual((None, None), python_check.run_code_block('None'))
        self.assertTupleEqual((None, None), python_check.run_code_block('pass'))

    def test_statement(self):
        self.assertTupleEqual(('bananagrams', None), python_check.run_code_block('print("bananagrams")'))
        self.assertTupleEqual(('', None), python_check.run_code_block('print("")'))
        self.assertTupleEqual(('\t', None), python_check.run_code_block('print("\t")'))
        self.assertTupleEqual((None, None), python_check.run_code_block('a = 1'))
        self.assertTupleEqual(('30', None), python_check.run_code_block('a = 15\nprint(a*2)'))

    def test_globals(self):
        globals_dict = dict()
        python_check.run_code_block('kljahoiebnjs = 20', globals_dict=globals_dict)
        self.assertTupleEqual(('20', None), python_check.run_code_block('print(kljahoiebnjs)', globals_dict=globals_dict))

    def test_errors(self):
        self.assertTupleEqual((None, 'IndexError'), python_check.run_code_block('a = "u"[44]'))
        self.assertTupleEqual(('j', 'TypeError'), python_check.run_code_block('print("j")\na = "b" * "c"'))

        normal_warning_function = python_check.logger.warning
        mock_stdout = ''

        def save_warning(msg):
            nonlocal mock_stdout
            mock_stdout += msg

        python_check.logger.warning = save_warning
        python_check.run_code_block('1/0')
        self.assertEqual('Caught error: division by zero from: 1/0. Continuing anyway...', mock_stdout)
        python_check.logger.warning = normal_warning_function

        # ToDo I feel like there's a good reason this doesn't work
        # self.assertEqual('\n', run_code('print("\\n")'))


class TestFormatting(unittest.TestCase):
    def test_everything_else(self):
        self.assertTupleEqual(('    some_key', 'some_val'),
                              python_check.indent_output('some_key', 'some_val'))
        self.assertTupleEqual(('    some_key', 'some_val\n              other_val'),
                              python_check.indent_output('some_key', 'some_val\nother_val'))
        self.assertTupleEqual(('    some_key', ''),
                              python_check.indent_output('some_key', None))

    def test_code_block(self):
        self.assertTupleEqual(('code_block', 'some_val'), python_check.indent_output('code_block', 'some_val'))


class TestMain(unittest.TestCase):
    code1 = {'attr': {'class': 'language-python'},
             'value': '1 is 1\n'}

    def test_main_function(self):
        # with mock.patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        normal_info_function = python_check.logger.info
        mock_stdout = ''

        def save_info(msg):
            nonlocal mock_stdout
            mock_stdout += msg

        python_check.logger.info = save_info

        with mock.patch('python_check.read_markdown') as mock_read_markdown:
            mock_read_markdown.return_value = {'doc': {'children': (self.code1,)}}
            python_check.main()

        python_check.logger.info = normal_info_function

        # mock_read_markdown.return_value.assert_called_with('20-feedback.md')
        self.assertEqual(10, mock_read_markdown.call_count)
        self.assertIn('Processing 20-feedback.md', mock_stdout)


if __name__ == '__main__':
    unittest.main()
