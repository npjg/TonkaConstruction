import os
import tempfile
import subprocess
import shutil

import pytest

from TonkaConstruction import Engine 

# This package includes a command that can be called from the command line,
# so we will store the name of that script here. It is defined in pyproject.toml,
# but I didn't see an easy way to reference that here, so we'll just hardcode it.
CALLABLE_SCRIPT_NAME = 'TonkaConstruction'

# The tests MUST be run from the root of the repository.
GAME_ROOT_DIRECTORY = 'tests/test_data'
game_directories = []
for filename in os.listdir(os.path.realpath(GAME_ROOT_DIRECTORY)):
    filepath = os.path.join(GAME_ROOT_DIRECTORY, filename)
    if os.path.isdir(filepath):
        game_directories.append(filepath)

def test_script_is_runnable():
        # RUN THE PYPIX2SVG SCRIPT.
        # We shell out rather than just calling the function from Python to make
        # sure that the script entry point is installed correctly too.
        # We don't need to actually process anything, just make sure the script runs.
        # So we can point it to an empty directory.
        empty_directory = tempfile.mkdtemp()
        try:
            # ATTEMPT TO RUN THE SCRIPT.
            command = [CALLABLE_SCRIPT_NAME, empty_directory]
            result = subprocess.run(command, capture_output = True, text = True)            

            # VERIFY THE SCRIPT RAN SUCCESSFULLY.
            if (result.returncode != 0):
                raise AssertionError(
                    f'Received a nonzero exit code when running `{CALLABLE_SCRIPT_NAME}` from command line!'
                    f'\nstdout: {result.stdout}'
                    f'\n\nstderr: {result.stderr}')
        finally:
            shutil.rmtree(empty_directory)

@pytest.mark.parametrize("game_directory_path", game_directories)
def test_process_game(game_directory_path):
    # PARSE THE RESOURCES.
    print(game_directory_path)
    temp_dir = tempfile.mkdtemp()
    try:
        Engine.main([game_directory_path, '--export', temp_dir])
        # TODO: Do something to verify the integrity of the created files.
    finally:
        shutil.rmtree(temp_dir)

# This isn't required for running the tests from the `pytest` command line,
# but it is useful to be able to debug tests in VS Code.
if __name__ == "__main__":
    pytest.main()
