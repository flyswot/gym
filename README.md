flyswot-gym
================

<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

`flyswot-gym` is a set of functions for helping to train
[`flyswot`](github.com/davanstrien/flyswot/) models. This is a WIP and
mainly intended for our particular workflow.

## 🚀 Training/updating a new flyswot model

These steps will also work for training other image classification
models thought the pipeline isn’t intended to cover all possible
scenarios to you may not get good results if you are doing something
very different.

### Loading our data

The data loading workflow described below assumes that you are working
with data structured in an image folder structure. In this structure
images are sorted into subdirectories with those directories
representing the label for that image. For example:

    Images/
        dogs/
            dog1.jpg
            dog2.jpg
        cats/
            cats1.jpg
            cats2.jpg

We use the Hugging Face hub to store the data we are going to use for
training. To upload our data from a local file system to the hub, see
the docs page on [preparing
data](https://flyswot.github.io/gym/loading_data.html) for flyswot.

## Training/updating a model

Once you have your data uploaded to the 🤗 hub we can train our or
update a new model. There is a notebok which helps us do this 🦾
<a href="https://colab.research.google.com/github/flyswot/gym/blob/master/flyswot_gym.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

## Using our model

For using a new model you can use
[flyswot](https://github.com/davanstrien/flyswot/). You can pass in the
model ID for your model to let `flyswot` know which model it should use
for making predictions.

    Usage: flyswot predict directory [OPTIONS] DIRECTORY CSV_SAVE_DIR

      Predicts against all images stored under DIRECTORY which match PATTERN in the
      filename.

      By default searches for filenames containing 'fs'.

      Creates a CSV report saved to `csv_save_dir`

    Arguments:
      DIRECTORY     Directory to start searching for images from  [required]
      CSV_SAVE_DIR  Directory used to store the csv report  [required]

    Options:
      --model-id TEXT       The model flyswot should use for making predictions
                            [default: flyswot/convnext-tiny-224_flyswot]
      --pattern TEXT        Pattern used to filter image filenames
      --bs INTEGER          Batch Size  [default: 16]
      --image-formats TEXT  Image format(s) to check  [default: .tif]
      --help                Show this message and exit.
