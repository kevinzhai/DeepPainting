import os
import shutil
from tqdm import tqdm


def sample_images(n, base_path, new_path=None, dir_keyword=None):
    """
    create a new directory with a subsample of the images in the current directory
    
    ex:
        base_path = '~/images'
        new_path = '~/images'
    """
    if not new_path:
        new_path = base_path + "-sample-" + str(n)
    os.makedirs(new_path, exist_ok=True)

    dirs = [x[0] for x in os.walk(base_path) if not x[0] == base_path]
    if dir_keyword:
        dirs = [x for x in dirs if dir_keyword in x]

    for absolute_dir in dirs:
        dir_ = absolute_dir.split('/')[-1]
        os.makedirs(os.path.join(new_path, dir_), exist_ok=True)
        files = os.listdir(absolute_dir)
        files = files[0:n]

        for file in tqdm(files):
            shutil.copyfile(os.path.join(base_path, dir_, file),
                            os.path.join(new_path, dir_, file))


if __name__ == "__main__":
    base_path = "/home/lab.analytics.northwestern.edu/echang/TEAMSHAREDFOLDER/flickr-64"
    sample_images(3000, base_path, dir_keyword="processed")
