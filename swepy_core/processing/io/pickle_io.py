import pickle


def load_pickle(path):
    """Return a content object from a pickle file"""
    with open(path, 'rb') as handle:
        return pickle.load(handle)


def save_pickle(content, path):
    """Pickle a content object"""
    with open(path, 'wb') as handle:
        pickle.dump(content, handle, protocol=pickle.HIGHEST_PROTOCOL)
