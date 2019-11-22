from util import Reporter, read_markdown, load_yaml, require
from unittest import TestCase, main

processed_markdown = read_markdown('bin/markdown_ast.rb',
                                   '_episodes/01-intro.md')


def code_and_expected_output(element_list):
    code_element = element_list[0]['children'][0]['value']
    code_start = code_element.find('~~~\n') + 4
    code_end = code_element.find('~~~', code_start)
    code = code_element[code_start:code_end]
    code = code.rstrip(' \n')

    output_element = element_list[1]['value']
    output = output_element.rstrip('\n')
    yield code, output


def run_code_check_output(code, output):
    pass


class TestCodeGenerator(TestCase):
    def test_generator_handles_list(self):
        code = {'attr': {'class': 'language-python'},
                'children': [{'type': 'text',
                              'value': 'Any Python interpreter can be used as a calculator:\n~~~\n3 + 5 * 4\n~~~'}]}
        output = {'type': 'codeblock',
                  'attr': {'class': 'output'},
                  'value': '23\n'}
        a, b = next(code_and_expected_output([code, output]))
        self.assertEqual('3 + 5 * 4', a)
        self.assertEqual('23', b)


class TestCodeExecutor(TestCase):
    def test_expression(self):
        self.assertEqual(True, run_code_check_output('3 + 5 * 4', 23))
        self.assertEqual(False, run_code_check_output('3 + 5 * 4', 24))


if __name__ == '__main__':
    main()

