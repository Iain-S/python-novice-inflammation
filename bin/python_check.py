from util import Reporter, read_markdown, load_yaml, require
import unittest
import sys
from io import StringIO
import numpy as np  # we'll need this as the lessons require it


class BadFormatException(Exception):
    pass


def get_code_and_output(element_list):
    code = None
    output = None

    for element in element_list:
        if element.get('attr') and \
                element['attr'].get('class') and \
                element['attr']['class'] == 'language-python':

            if code:
                # Two code blocks in a row
                yield code, output
                output = None

            try:
                code_element = element['children'][0]['value']
                code_start = code_element.find('~~~\n') + 4
                code_end = code_element.find('~~~', code_start)
                code = code_element[code_start:code_end]
            except KeyError:
                code = element['value']

            code = code[:-1]  # .rstrip(' \n')

        elif element.get('attr') and \
                element['attr'].get('class') and \
                element['attr']['class'] == 'output':

            if output:
                raise BadFormatException("Two output elements in a row.",
                                         element)

            if not code:
                raise BadFormatException("There should always be "
                                         "code before output")

            output_element = element['value']
            output = output_element[:-1]  # .rstrip('\n')

            yield code, output
            code = None
            output = None


def run_code(code, *args):
    if code in ('None', 'pass'):
        return None

    # ToDo Use contextlib redirect_stdout
    real_stdout = sys.stdout
    sys.stdout = StringIO()
    return_value = None
    try:
        return_value = eval(code, *args)
    except SyntaxError:
        # Assume that code is a statement, such as "a = 1", and execute it
        exec(code, *args)

    if return_value is None:
        code_output = sys.stdout.getvalue()

        if code_output == '':
            # Leave it as None
            pass
        elif code_output == '\n':
            # Special case for, e.g., print("")
            return_value = ''
        else:
            # Strip \n from the end
            return_value = code_output[0:-1]
            # return_value = code_output.rstrip('\n')

    elif type(return_value) == str:
        return_value = "'" + return_value + "'"
    else:
        return_value = str(return_value)

    sys.stdout = real_stdout
    return return_value


# def run_code_check_output(code, output):
#     eval_value = run_code(code)
#     return eval_value == output


def main():
    processed_markdown = read_markdown('bin/markdown_ast.rb',
                                       '_episodes/01-intro.md')

    elements = processed_markdown['doc']['children']
    globals_dict = dict()
    for code, output in get_code_and_output(elements):
        actual_output = run_code(code)
        if output and output != actual_output:
            print('Expected: {}\nActual:{}\n\n'.format(output, actual_output))


class TestCodeGenerator(unittest.TestCase):
    code1 = {'attr': {'class': 'language-python'},
            'children': [{'type': 'text',
                          'value': 'Any Python interpreter can be used as '
                                   'a calculator:\n~~~\n3 + 5 * 4\n~~~'}]}
    output1 = {'type': 'codeblock',
              'attr': {'class': 'output'},
              'value': '23\n'}
    code2 = {'attr': {'class': 'language-python'},
            'children': [{'type': 'text',
                          'value': '~~~\n21 / 7\n~~~'}]}
    output2 = {'type': 'codeblock',
              'attr': {'class': 'output'},
              'value': '3\n'}


    def test_generator_handles_list(self):
        document_iterator = get_code_and_output([self.code1, self.output1,
                                                 self.code2, self.output2])
        a, b = next(document_iterator)
        self.assertEqual('3 + 5 * 4', a)
        self.assertEqual('23', b)

        a, b = next(document_iterator)
        self.assertEqual('21 / 7', a)
        self.assertEqual('3', b)

    def test_raises_errors(self):
        document_iterator = get_code_and_output([self.output1])
        self.assertRaises(BadFormatException, lambda: next(document_iterator))

        document_iterator = get_code_and_output([self.code1, self.output1,
                                                 self.output1])
        next(document_iterator)
        self.assertRaises(BadFormatException, lambda: next(document_iterator))


class TestCodeExecutor(unittest.TestCase):
    def test_expression(self):
        self.assertEqual('23', run_code('3 + 5 * 4'))
        self.assertEqual("'t'", run_code('"t"'))

    def test_none_pass(self):
        self.assertEqual(None, run_code('None'))
        self.assertEqual(None, run_code('pass'))

    def test_statement(self):
        self.assertEqual('bananagrams', run_code('print("bananagrams")'))
        self.assertEqual('', run_code('print("")'))
        self.assertEqual('\t', run_code('print("\t")'))
        self.assertEqual(None, run_code('a = 1'))
        self.assertEqual('30', run_code('a = 15\nprint(a*2)'))

    def test_globals(self):
        run_code('kljahoiebnjs = 20')
        self.assertEqual('20', run_code('print(kljahoiebnjs)'))


        # ToDo I feel like there's a good reason this doesn't work
        # self.assertEqual('\n', run_code('print("\\n")'))


if __name__ == '__main__':
    unittest.main()
    # main()
