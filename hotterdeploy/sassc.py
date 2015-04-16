#pip install pyScss

from scss.compiler import Compiler, compile_file



def compile(file_name):
    #data = Compiler().compile_string("a { color: red + green; }")
    data = compile_file(file_name)
    return data



'''
import sass


print '-----------'
data = sass.compile(filename=event.src_path,
                    output_style='nested',
                    include_paths=os.path.dirname(event.src_path))
print '-----------'
'''
