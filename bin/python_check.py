import re
import unittest
import sys
from bin.util import read_markdown
from io import StringIO

# Check numpy and matplotlib are installed as they are used in the lesson
import numpy  # noqa: F401
import matplotlib  # noqa: F401


class BadFormatError(Exception):
    pass


def is_python_block(element):
    return element.get('attr') and element['attr'].get('class') and element['attr']['class'] == 'language-python'


def is_output_block(element):
    return element.get('attr') and element['attr'].get('class') and element['attr']['class'] == 'output'


def is_error_block(element):
    return element.get('attr') and element['attr'].get('class') and element['attr']['class'] == 'error'


def get_code_output_and_error(element_list):
    """The element_list represents an episode with various kinds of code and text.  When we find a group of
       python-output-error, python-output, python-error or python blocks, return them."""
    code = None
    output = None
    error = None

    for element in element_list:
        if is_python_block(element):

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

        elif is_output_block(element):

            if output:
                # ToDo 07-func.md does, legitimately, have multiple consecutive outputs
                raise BadFormatError("Two output elements in a row.", element)

            if not code:
                raise BadFormatError("There should always be code before output")

            output_element = element['value']
            output = output_element[:-1]  # .rstrip('\n')

        elif is_error_block(element):

            if not code:
                raise BadFormatError("Code should preceed Error")

            # e.g. TypeError
            match = re.search(r'\w*Error\b', element['value'])
            error = match.group(0)

    if code:
        yield code, output, error


def run_code_block(code, globals_dict=None):
    """Given some Python code as a string, try to run it and return any output or errors."""

    if code in ('None', 'pass'):
        return None, None

    # ToDo Use contextlib redirect_stdout
    real_stdout = sys.stdout
    sys.stdout = StringIO()
    return_value = None
    return_error = None
    real_error_msg = None

    try:
        try:
            return_value = eval(code, globals_dict)
        except SyntaxError:
            # Assume that code is a statement, such as "a = 1", and execute it
            exec(code, globals_dict)
    except Exception as e:
        if type(e) in (IndexError, TypeError, SyntaxError, IndentationError, AssertionError, NameError):
            return_error = re.search(r'\w*Error\b', str(type(e))).group(0)
        else:
            real_error_msg = 'Caught error: {} from: {}. Continuing anyway...'.format(e, code)

    # if eval() didn't return anything, get output from redirected stdout
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

    elif type(return_value) == str:
        return_value = "'" + return_value + "'"
    else:
        return_value = str(return_value)

    sys.stdout = real_stdout

    if real_error_msg:
        # Now that print works again
        print(real_error_msg)

    return return_value, return_error


def run_episode(md_elements, element_parser=get_code_output_and_error, code_runner=run_code_block):
    """Given a sequence of markdown elements for an episode, extract python code, expected outputs and expected errors.
       Run the code and verify that it does give the expected output / raise the anticipated errors."""
    globals_dict = dict()
    code_runs = []
    for i, (code, output, error) in enumerate(element_parser(md_elements)):
        this_run = {'code_block': i+1}
        actual_output, actual_error = code_runner(code, globals_dict=globals_dict)
        if output and output != actual_output:
            this_run['code'] = code
            this_run['expected_output'] = output
            this_run['actual_output'] = actual_output
        if error and error != actual_error:
            this_run['code'] = code
            this_run['expected_error'] = error
            this_run['actual_error'] = actual_error
        code_runs.append(this_run)
    return code_runs


def indent_output(key, value):
    """Formats key and value for printing"
       code_block: 12
           any_other_key: value_line_1
                          value_line_2"""
    if key == 'code_block':
        return key, value

    else:
        # Indent the key by four spaces
        indent = ' ' * 4
        return_key = indent + key

        # For any value after the first, indent by four spaces + the length of key + 2 (for the ": ")
        padding = ' ' * (len(key) + 2)
        value_lines = value.split('\n')

        return_value = value_lines[0]

        for line in value_lines[1:]:
            return_value += '\n' + indent + padding + line

        return return_key, return_value


def main():
    """For each episode, process the markdown and run the episode.  Format and print the output."""
    # ToDo Test main()
    for doc in (
            # '01-intro.md', '02-numpy.md', '03-loop.md', '04-lists.md',
            # '05-files.md',
            # '06-cond.md',
            # '07-func.md',
            # '08-errors.md',
            '09-defensive.md',
            # '10-debugging.md',
            # '11-cmdline.md',
            ):

        print("Processing", doc)
        doc = '_episodes/' + doc
        processed_markdown = read_markdown('bin/markdown_ast.rb', doc)
        elements = processed_markdown['doc']['children']

        problems = run_episode(elements)

        for problem in problems:
            for key, value in problem.items():
                print('{}: {}'.format(*indent_output(key, value)))


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
                             run_episode((), yield_good_elements, run_some_code)[0])
        self.assertDictEqual({'code_block': 1, 'code': 'some code', 'expected_error': 'wrong error', 'actual_error': 'some error'},
                             run_episode((), yield_wrong_error, run_some_code)[0])
        self.assertDictEqual({'code_block': 1, 'code': 'some code', 'expected_output': 'wrong output', 'actual_output': 'some output'},
                             run_episode((), yield_wrong_output, run_some_code)[0])


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
        document_iterator = get_code_output_and_error([self.code1, self.output1,
                                                       self.code2, self.output2, self.error2])
        a, b, c = next(document_iterator)
        self.assertEqual('3 + 5 * 4', a)
        self.assertEqual('23', b)
        self.assertIsNone(c)

        a, b, c = next(document_iterator)
        self.assertEqual('21 / 7', a)
        self.assertEqual('3', b)
        self.assertEqual('TypeError', c)

    def test_raises_errors(self):
        document_iterator = get_code_output_and_error([self.output1])
        self.assertRaises(BadFormatError, lambda: next(document_iterator))

        document_iterator = get_code_output_and_error([self.code1, self.output1, self.output1])
        self.assertRaises(BadFormatError, lambda: next(document_iterator))


class TestCodeExecutor(unittest.TestCase):
    def test_expression(self):
        self.assertTupleEqual(('23', None), run_code_block('3 + 5 * 4'))
        self.assertTupleEqual(("'t'", None), run_code_block('"t"'))

    def test_none_pass(self):
        self.assertTupleEqual((None, None), run_code_block('None'))
        self.assertTupleEqual((None, None), run_code_block('pass'))

    def test_statement(self):
        self.assertTupleEqual(('bananagrams', None), run_code_block('print("bananagrams")'))
        self.assertTupleEqual(('', None), run_code_block('print("")'))
        self.assertTupleEqual(('\t', None), run_code_block('print("\t")'))
        self.assertTupleEqual((None, None), run_code_block('a = 1'))
        self.assertTupleEqual(('30', None), run_code_block('a = 15\nprint(a*2)'))

    def test_globals(self):
        globals_dict = dict()
        run_code_block('kljahoiebnjs = 20', globals_dict=globals_dict)
        self.assertTupleEqual(('20', None), run_code_block('print(kljahoiebnjs)', globals_dict=globals_dict))

    def test_errors(self):
        self.assertTupleEqual((None, 'IndexError'), run_code_block('a = "u"[44]'))
        self.assertTupleEqual(('j', 'TypeError'), run_code_block('print("j")\na = "b" * "c"'))

        # ToDo I feel like there's a good reason this doesn't work
        # self.assertEqual('\n', run_code('print("\\n")'))


class TestFormatting(unittest.TestCase):
    def test_everything_else(self):
        self.assertTupleEqual(('    some_key', 'some_val'), indent_output('some_key', 'some_val'))
        self.assertTupleEqual(('    some_key', 'some_val\n              other_val'), indent_output('some_key', 'some_val\nother_val'))

    def test_code_block(self):
        self.assertTupleEqual(('code_block', 'some_val'), indent_output('code_block', 'some_val'))


if __name__ == '__main__':
    # unittest.main()
    main()
