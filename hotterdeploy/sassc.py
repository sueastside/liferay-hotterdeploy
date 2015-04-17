#pip install pyScss

from scss.compiler import Compiler, compile_file
from scss.errors import SassEvaluationError

class SassException(Exception):
    def __init__(self, cause):
        super(SassException).__init__(cause)



def compile(file_name):
    #data = Compiler().compile_string("a { color: red + green; }")
    try:
        data = compile_file(file_name)
        return data
    except SassEvaluationError as e:
        raise SassException(e)



'''
import sass


print '-----------'
data = sass.compile(filename=event.src_path,
                    output_style='nested',
                    include_paths=os.path.dirname(event.src_path))
print '-----------'
'''
