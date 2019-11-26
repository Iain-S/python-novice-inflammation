import re

from util import Reporter, read_markdown, load_yaml, require
import unittest
import sys
from io import StringIO
import numpy as np  # we'll need this as the lessons require it
import matplotlib  # ToDo Add NoQA for flake8


class BadFormatError(Exception):
    pass


def get_code_and_output(element_list):
    code = None
    output = None
    error = None

    for element in element_list:
        if element.get('attr') and \
                element['attr'].get('class') and \
                element['attr']['class'] == 'language-python':

            if code:
                # Two code blocks in a row
                yield code, output, error
                output = None
                error = None

            try:
                code_element = None
                for child in element['children']:
                    if child['value'].count('~~~') == 2:
                        code_element = child['value']
                        break
                    elif child['value'].count('~~~') == 1 and not code_element:
                        code_element = child['value']
                    elif child['value'].count('~~~') == 1 and code_element:
                        code_element += child['value']
                        break
                    elif code_element:
                        if child['value'] == 'lsquo' or \
                                child['value'] == 'rsquo':
                            code_element += "'"
                        else:
                            code_element += child['value']


                code_start = code_element.find('~~~\n') + 4
                code_end = code_element.find('~~~', code_start)
                if code_end == -1:
                    raise BadFormatError('There should be a closing ~~~.')
                code = code_element[code_start:code_end]
            except KeyError:
                code = element['value']

            code = code[:-1]  # .rstrip(' \n')

        elif element.get('attr') and \
                element['attr'].get('class') and \
                element['attr']['class'] == 'output':

            if output:
                raise BadFormatError("Two output elements in a row.",
                                     element)

            if not code:
                raise BadFormatError("There should always be "
                                         "code before output")

            output_element = element['value']
            output = output_element[:-1]  # .rstrip('\n')

        elif element.get('attr') and \
                element['attr'].get('class') and \
                element['attr']['class'] == 'error':

            if not code:
                raise BadFormatError("Code should preceed Error")

            # e.g. TypeError
            match = re.search(r'\w*Error\b', element['value'])
            error = match.group(0)

    if code:
        yield code, output, error


def run_code(code, *args):
    if code in ('None', 'pass'):
        return None

    # ToDo Use contextlib redirect_stdout
    real_stdout = sys.stdout
    sys.stdout = StringIO()
    return_value = None

    try:
        try:
            return_value = eval(code, *args)
        except SyntaxError:
            # Assume that code is a statement, such as "a = 1", and execute it
            exec(code, *args)
    except (IndexError, TypeError, SyntaxError) as e:
        print('Caught error: {}\nContinuing anyay...'.format(e))

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
    # ToDo Test main()
    processed_markdown = read_markdown('bin/markdown_ast.rb',
                                       '_episodes/03-loop.md')

    elements = processed_markdown['doc']['children']
    globals_dict = dict()
    for code, output in get_code_and_output(elements):
        actual_output = run_code(code, globals_dict)
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
                          'value': '~~~\n21 / 7\n~~~'}]}
    output2 = {'type': 'codeblock',
              'attr': {'class': 'output'},
              'value': '3\n'}
    error2 = {'type': 'codeblock',
              'attr': {'class': 'error'},
              'value': '-' * 75 + '\nTypeError'}

    def test_generator_handles_list(self):
        document_iterator = get_code_and_output([self.code1, self.output1,
                                                 self.code2, self.output2,
                                                 self.error2])
        a, b, c = next(document_iterator)
        self.assertEqual('3 + 5 * 4', a)
        self.assertEqual('23', b)
        self.assertIsNone(c)

        a, b, c = next(document_iterator)
        self.assertEqual('21 / 7', a)
        self.assertEqual('3', b)
        self.assertEqual('TypeError', c)

    # def test_raises_errors(self):
    #     document_iterator = get_code_and_output([self.output1])
    #     self.assertRaises(BadFormatError, lambda: next(document_iterator))
    #
    #     document_iterator = get_code_and_output([self.code1, self.output1,
    #                                              self.output1])
    #     next(document_iterator)
    #     self.assertRaises(BadFormatError, lambda: next(document_iterator))

    # ToDo Handle "Error" blocks in the markdown


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
        globals_dict = dict()
        run_code('kljahoiebnjs = 20', globals_dict)
        self.assertEqual('20', run_code('print(kljahoiebnjs)', globals_dict))


        # ToDo I feel like there's a good reason this doesn't work
        # self.assertEqual('\n', run_code('print("\\n")'))


if __name__ == '__main__':
    unittest.main()
    # main()
