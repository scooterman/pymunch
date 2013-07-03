
from munch.targets import cpp

inttype = cpp.cpp_type('int')
inttype.spelling += ['int32_t', 'uint32_t']

longtype = cpp.cpp_type('long')
longtype.spelling += ['int64_t', 'uint64_t']