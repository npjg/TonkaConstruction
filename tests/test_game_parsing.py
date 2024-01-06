import pytest
import os
import tempfile
import shutil

from TonkaConstruction import Engine 

# The tests MUST be run from the root of the repository.
GAME_ROOT_DIRECTORY = 'tests/test_data'
game_directories = []
for filename in os.listdir(os.path.realpath(GAME_ROOT_DIRECTORY)):
    filepath = os.path.join(GAME_ROOT_DIRECTORY, filename)
    if os.path.isdir(filepath):
        game_directories.append(filepath)

@pytest.mark.parametrize("game_directory_path", game_directories)
def test_process_game(game_directory_path):
    # PARSE THE RESOURCES.
    print(game_directory_path)
    temp_dir = tempfile.mkdtemp()
    try:
        Engine.main([game_directory_path, '--export', temp_dir])
    finally:
        shutil.rmtree(temp_dir)

# This isn't required for running the tests from the `pytest` command line,
# but it is useful to be able to debug tests in VS Code.
if __name__ == "__main__":
    pytest.main()
