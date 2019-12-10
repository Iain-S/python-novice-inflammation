# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import re
import sys
import logging
from os.path import join, isdir
from os import listdir
from argparse import ArgumentParser
from util import read_markdown
from io import StringIO
from contextlib import redirect_stdout
from difflib import Differ

# Check numpy and matplotlib are installed as they are used in the inflammation lesson
import numpy  # noqa: F401
import matplotlib  # noqa: F401

# Check pandas is installed as it is used in the gapminder lesson
import pandas  # noqa: F401


logging.basicConfig()
logger = logging.getLogger('python_check')


# Todo run all of inflammation
# Todo logging formatting
# ToDo refactor the large functions
class BadFormatError(Exception):
    pass


def is_element_of_class(element, md_class_name):
    return element.get('attr') and element['attr'].get('class') and element['attr']['class'] == md_class_name


def get_code_output_and_error(element_list):
    """The element_list represents an episode with various kinds of code and text.  When we find a group of
       python-output-error, python-output, python-error or python blocks, return them."""
    code = None
    output = None
    error = None

    for element in element_list:
        if is_element_of_class(element, 'language-python'):

            if code:
                # Two code blocks in a row
                yield code, output, error
                output = None
                error = None

            if 'value' in element:
                code = element['value']
            else:
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

            code = code[:-1]  # .rstrip(' \n')

        elif is_element_of_class(element, 'output'):

            if output:
                # ToDo 07-func.md does, legitimately, have multiple consecutive outputs
                raise BadFormatError("Two output elements in a row.", element)

            if not code:
                raise BadFormatError("There should always be code before output")

            output_element = element['value']
            output = output_element[:-1]  # .rstrip('\n')

        elif is_element_of_class(element, 'error'):

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

    temp_stdout = StringIO()
    with redirect_stdout(temp_stdout):
        return_value = None
        return_error = None
        real_error_msg = None

        try:
            try:
                return_value = eval(code, globals_dict)
            except SyntaxError:
                # A SyntaxError could mean that that the code is a statement, such as "a = 1"
                # In that case, we use exec instead of eval
                exec(code, globals_dict)
        except Exception as e:
            # These are the types of errors we expect from the lesson code
            if type(e) in (IndexError, TypeError, SyntaxError, IndentationError, AssertionError, NameError):
                return_error = re.search(r'\w*Error\b', str(type(e))).group(0)
            else:
                real_error_msg = 'Caught error: {} from: {}. Continuing anyway...'.format(e, code)

        # If eval() didn't return anything, get output from redirected stdout
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

    if real_error_msg:
        # Now that output works normally again
        logger.warning(real_error_msg)

    return return_value, return_error


def run_episode(md_elements, element_parser=get_code_output_and_error, code_runner=run_code_block):
    """Given a sequence of markdown elements, extract python code, expected outputs and expected errors.
       Run the code and verify that it does give the expected output / raise the anticipated errors."""
    globals_dict = dict()
    code_runs = []
    for i, (code, expected_output, expected_error) in enumerate(element_parser(md_elements)):
        this_run = {'code_block': i+1}

        actual_output, actual_error = code_runner(code, globals_dict=globals_dict)

        differ = Differ()

        if expected_output and expected_output != actual_output:
            this_run['code'] = code
            this_run['expected_output'] = expected_output
            this_run['actual_output'] = actual_output
            this_run['output_diff'] = list(differ.compare(expected_output.splitlines(keepends=True),
                                                          actual_output.splitlines(keepends=True)))

        if expected_error and expected_error != actual_error:
            this_run['code'] = code
            this_run['expected_error'] = expected_error
            this_run['actual_error'] = actual_error
            this_run['error_diff'] = list(differ.compare(expected_error.splitlines(keepends=True),
                                                           actual_error.splitlines(keepends=True)))

        code_runs.append(this_run)

    return code_runs


def indent_output(key, value):
    """Formats key and value for printing"
       code_block: 12
           any_other_key: value_line_1
                          value_line_2"""
    value = '' if value is None else value

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


def parse_args(args):
    """Parse the command line arguments, returning a tuple:
       (stop on error, verbose output, list of files to process)"""

    parser = ArgumentParser(description="check the Python in markdown files.")
    parser.add_argument('directory', type=str, help="check all .md files in this directory, unless -f is used")
    parser.add_argument('-f', type=str, nargs='*', help="a list of filenames to check in directory")
    parser.add_argument('-v', required=False, type=bool, default=False, help="give verbose output")
    # ToDo We could add this to fail after the first error in a lesson
    # parser.add_argument('-s', required=False, type=bool, default=False, help="stop if an error occurs")

    arguments = parser.parse_args(args)

    assert isdir(arguments.directory)

    if arguments.f:
        files = [join(arguments.directory, file) for file in arguments.f]
    else:
        files = [join(arguments.directory, file) for file in listdir(arguments.directory) if file.endswith('.md')]

    return arguments.v, files

        # (
        #     # '01-intro.md', '02-numpy.md', '03-loop.md', '04-lists.md',
        #     # '05-files.md',
        #     # '06-cond.md',
        #     # '07-func.md',
        #     # '08-errors.md',
        #     # '09-defensive.md',
        #     # '10-debugging.md',
        #     # '11-cmdline.md',
        #     # '01-run-quit.md',
        #     # '02-variables.md',
        #     # '03-types-conversion.md',
        #     # '04-built-in.md',
        #     # '05-coffee.md',
        #     # '06-libraries.md',
        #     # '07-reading-tabular.md',
        #     # '08-data-frames.md',
        #     # '09-plotting.md',
        #     # '10-lunch.md',
        #     '11-lists.md',
        #     '12-for-loops.md',
        #     '13-looping-data-sets.md',
        #     '14-writing-functions.md',
        #     '15-scope.md',
        #     '16-coffee.md',
        #     '17-conditionals.md',
        #     '18-style.md',
        #     '19-wrap.md',
        #     '20-feedback.md'
        #     )


def main():
    """For each episode, process the markdown and run the episode.  Format and print the output."""

    verbose_output, files = parse_args(sys.argv[1:])

    if verbose_output:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    for file in files:

        logger.info("Processing {}".format(file))
        processed_markdown = read_markdown('bin/markdown_ast.rb', file)
        elements = processed_markdown['doc']['children']

        results = run_episode(elements)

        for result in results:
            for key, value in result.items():
                if key == 'code_block':
                    logger.info('{}: {}'.format(key, value if value else ''))
                elif key == 'code':
                    logger.warning('code')
                    for line in value.splitlines():
                        logger.warning('    '+line)
                elif key.endswith('diff'):
                    logger.warning(key)
                    for line in value:
                        logger.warning('    '+line.rstrip())

    # ToDo exit(errors)


if __name__ == '__main__':
    main()  # pragma: no cover
