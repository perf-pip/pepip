from pathlib import Path
import shutil


def delete_dir_recursion(p):
    """
    Delete folder, sub-folders and files.
    """
    for f in p.glob('**/*'):
        if f.is_symlink():
            f.unlink(missing_ok=True)  # missing_ok is added in python 3.8
            print(f'symlink {f.name} from path {f} was deleted')
        elif f.is_file():
            f.unlink()
            print(f'file: {f.name} from path {f} was deleted')
        elif f.is_dir():
            try:
                f.rmdir()  # delete empty sub-folder
                print(f'folder: {f.name} from path {f} was deleted')
            except OSError:  # sub-folder is not empty
                delete_dir_recursion(f)  # recurse the current sub-folder
            except Exception as exception:  # capture other exception
                print(f'exception name: {exception.__class__.__name__}')
                print(f'exception msg: {exception}')

    try:
        p.rmdir()  # time to delete an empty folder
        print(f'folder: {p.name} from path {p} was deleted')
    except NotADirectoryError:
        p.unlink()  # delete folder even if it is a symlink, linux
        print(f'symlink folder: {p.name} from path {p} was deleted')
    except Exception as exception:
        print(f'exception name: {exception.__class__.__name__}')
        print(f'exception msg: {exception}')


def delete_dir(folder):
    p = Path(folder)

    if not p.exists():
        print(f'The path {p} does not exists!')
        return

    # Attempt to delete the whole folder at once.
    try:
        shutil.rmtree(p)
    except Exception as exception:
        print(f'exception name: {exception.__class__.__name__}')
        print(f'exception msg: {exception}')
        # continue parsing the folder
    else:  # else if no issues on rmtree()
        if not p.exists():  # verify
            print(f'folder {p} was successfully deleted by shutil.rmtree!')
            return

    print(f'Parse the folder {folder} ...')
    delete_dir_recursion(p)

    if not p.exists():  # verify
        print(f'folder {p} was successfully deleted!')
