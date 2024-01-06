#define PY_SSIZE_T_CLEAN
#include <Python.h>

/// Actually decompresses the PackBits stream, and easily provides a 10x performance improvement
/// over the pure Python implementation.
static PyObject *method_decompress_pack_bits(PyObject *self, PyObject *args) {
    // READ THE PARAMETERS FROM PYTHON.
    PyBytesObject *compressed_image_data_object = NULL;
    char *compressed_image_data = NULL;
    unsigned int compressed_image_data_size = 0;
    unsigned int uncompressed_image_data_size = 0;
    if(!PyArg_ParseTuple(args, "SII", &compressed_image_data_object, &compressed_image_data_size, &uncompressed_image_data_size)) {
        return NULL;
    }

    // ALLOCATE THE UNCOMPRESSED PIXELS BUFFER.
    char *uncompressed_image_data = malloc(uncompressed_image_data_size + 1);
    unsigned int uncompressed_data_index = 0;

    // DECOMPRESS THIS IMAGE.
    compressed_image_data = PyBytes_AsString(compressed_image_data_object);
    unsigned int compressed_data_index = 0;
    while ((compressed_data_index < compressed_image_data_size) && (uncompressed_data_index < uncompressed_image_data_size)) {
        // TAKE THE NEXT OPERATION.
        char operation_byte = compressed_image_data[compressed_data_index++];
        if (operation_byte >= 0 && operation_byte <= 127) {
            // READ AN UNCOMPRESSED RUN.
            // An operation byte inclusively between 0x00 (+0) and 0x7f (+127) indicates
            // an uncompressed run of the value of the operation byte plus one.
            unsigned int run_length = operation_byte + 1;
            memcpy(&uncompressed_image_data[uncompressed_data_index], &compressed_image_data[compressed_data_index], run_length);
            uncompressed_data_index += run_length;
            compressed_data_index += run_length;
        } else {
            // EXPAND THIS COMPRESSED RUN.
            // An operation byte inclusively between 0x81 (-127) and 0xff (-1) indicates
            // the next byte is a color that should be repeated for a run of (-n+1) pixels.
            unsigned int color_index = compressed_image_data[compressed_data_index++];
            unsigned int run_length = -operation_byte + 1;
            for (unsigned int run_index = 0; run_index < run_length; run_index++) {
                uncompressed_image_data[uncompressed_data_index] = color_index;
                uncompressed_data_index += 1;
            }
        }
    }

    // RETURN THE DECOMPRESSED PIXELS TO PYTHON.
    PyObject *return_value = Py_BuildValue("y#", uncompressed_image_data, uncompressed_image_data_size);

    // FREE THE DECOMPRESSED PIXELS.
    free(uncompressed_image_data);
    return return_value;
}


/// Defines the Python methods callable in this module.
static PyMethodDef PackBitsDecompressionMethod[] = {
    {"decompress", method_decompress_pack_bits, METH_VARARGS, "Decompresses raw PackBits-encoded streams."},
    // An entry of nulls must be provided to indicate we're done.
    {NULL, NULL, 0, NULL}
};

/// Defines the Python module itself. Because the module requires references to 
/// each of the methods, the module must be defined after the methods.
static struct PyModuleDef PackBitsModule = {
    PyModuleDef_HEAD_INIT,
    "PackBits",
    "Python interface for interacting with raw PackBits-encoded streams. Currently only decompression is supported.",
    // A negative value indicates that this module doesn’t have support for sub-interpreters.
    // A non-negative value enables the re-initialization of your module. It also specifies 
    // the memory requirement of your module to be allocated on each sub-interpreter session.
    -1,
    PackBitsDecompressionMethod
};

/// Called when a Python script inputs this module for the first time.
PyMODINIT_FUNC PyInit_PackBits(void) {
    return PyModule_Create(&PackBitsModule);
}
