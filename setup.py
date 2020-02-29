from distutils.core import setup
from Cython.Build import cythonize

# Ensure you have Cython installed, obviously. pip is adequate.
# To run this, the cmdline args are: `python3 setup.py build_ext --inplace`
setup(
    name='OOTR app',
    ext_modules=cythonize(
        module_list=["Search.pyx", "Entrance.pyx", "EntranceShuffle.pyx",  "State.pyx", "Fill.pyx", "Hints.pyx", "World.pyx", "Location.pyx", "Main.pyx"],
        compiler_directives={'language_level': 3})
)
