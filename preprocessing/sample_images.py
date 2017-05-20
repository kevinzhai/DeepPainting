import os
import shutil
import random
from tqdm import tqdm


def sample_images(n, base_path, new_path=None, dir_keyword=None):
    """
    create a new directory with a subsample of the images in the current directory
    
    ex:
        base_path = '~/project/images'
        new_path = '~/project/images-sample-1000'
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


def create_train_test_dirs(path, train_test_split):
    """
    create train and test directories given a splitting proportion as a tuple
    e.g. train_test_split = (.8, .2)
    """
    assert train_test_split[0] + train_test_split[1] == 1, "split must sum to 1"

    train_dir = os.path.join(path, 'train')
    test_dir = os.path.join(path, 'test')
    os.makedirs(train_dir)
    os.makedirs(test_dir)

    dirs = []
    for d in next(os.walk(path))[1]:
        if d not in ['train', 'test']:
            dirs.append(d)

    for dir_ in dirs:
        os.makedirs(os.path.join(train_dir, dir_), exist_ok=True)
        os.makedirs(os.path.join(test_dir, dir_), exist_ok=True)
        files = os.listdir(os.path.join(path, dir_))
        train_files = set(random.sample(files, round(len(files) * train_test_split[0])))
        test_files = [f for f in files if f not in train_files]
        for f in train_files:
            shutil.copyfile(os.path.join(path, dir_, f), os.path.join(train_dir, dir_, f))
        for f in test_files:
            shutil.copyfile(os.path.join(path, dir_, f), os.path.join(test_dir, dir_, f))


if __name__ == "__main__":
    pass