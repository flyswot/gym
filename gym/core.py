# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_core.ipynb.

# %% auto 0
__all__ = ['filter_bad_images', 'get_fpath', 'return_base_path_deduplicated', 'check_uniques', 'drop_duplicates', 'get_id',
           'split_w_stratify', 'train_valid_split_w_stratify', 'prepare_dataset', 'prepare_transforms', 'FlyswotData',
           'prep_data', 'collate_fn', 'train_model', 'plot_confusion_matrix', 'create_classification_report',
           'create_test_results_df', 'create_mistakes_image_navigator', 'create_misclassified_report']

# %% ../nbs/00_core.ipynb 3
import re

# %% ../nbs/00_core.ipynb 4
import transformers
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from dataclasses import asdict
from collections import OrderedDict
from typing import Union, Tuple, Sequence, Set
from numpy.random import RandomState
import numpy as np
from datasets import Dataset
from datasets import load_dataset
from pathlib import Path
from sklearn.model_selection import StratifiedShuffleSplit
from torchvision.transforms import (CenterCrop, 
                                    RandomErasing,
                                    RandomAutocontrast,
                                    Compose, 
                                    Normalize, 
                                    RandomHorizontalFlip,
                                    RandomResizedCrop, 
                                    Resize, 
                                    RandomAdjustSharpness,
                                    ToTensor)
import torch
from transformers import AutoFeatureExtractor, TrainingArguments, Trainer
from transformers import AutoModelForImageClassification
from evaluate import load as load_metric
from rich import print
import re
from dataclasses import dataclass
from typing import Dict
import datasets
import pandas as pd
from scipy.special import softmax
from tqdm.auto import tqdm
from imagededup.methods import PHash
from PIL import Image

# %% ../nbs/00_core.ipynb 24
def filter_bad_images(ds: Dataset):
    idx = list(range(len(ds)))
    for i in tqdm(idx):
        try:
            if isinstance(ds[i]['image'], Image.Image):
                continue
            else:
                idx.pop(i)
        except OSError:
            idx.pop(i)
    return ds.select(idx)


# %% ../nbs/00_core.ipynb 27
def get_fpath(ds: Dataset):
   return ds.map(lambda x: {'fpath': x['image'].filename})

# %% ../nbs/00_core.ipynb 34
def return_base_path_deduplicated(x):
    f = x['fpath']
    f = re.sub(r"(\(\d\))","",f)
    f = f.split(".")[0]
    f = f.rstrip()
    return {"clean_path": re.sub(r"(\(\d\))","",f)}

# %% ../nbs/00_core.ipynb 35
def check_uniques(example, uniques, column='clean_path'):
    if example[column] in uniques:
        uniques.remove(example[column])
        return True
    else:
        return False

# %% ../nbs/00_core.ipynb 36
def drop_duplicates(ds):
    ds = ds.map(return_base_path_deduplicated)
    uniques = set(ds['clean_path'])
    ds = ds.filter(check_uniques, fn_kwargs={"uniques":uniques})
    return ds

# %% ../nbs/00_core.ipynb 39
def get_id(example):
    x = example["fpath"]
    x = Path(x).name.split("_")
    return {"id": "_".join(x[:2] if len(x) >= 3 else x[:3])}

# %% ../nbs/00_core.ipynb 41
def split_w_stratify(
    ds,
    test_size: Union[int, float],
    random_state: Union[int, RandomState, None] = None,
) -> Tuple[Dataset, Dataset]:
    labels = ds['label']
    label_array = np.array(labels)
    train_inds, valid_inds = next(
        StratifiedShuffleSplit(
            n_splits=3, test_size=test_size, random_state=random_state
        ).split(np.zeros(len(labels)), y=label_array)
    )
    return ds.select(train_inds), ds.select(valid_inds)

# %% ../nbs/00_core.ipynb 49
def train_valid_split_w_stratify(
    ds,
    valid_size: Union[int,float]=None,
    test_size: Union[int, float]=0.2,
    train_size: Union[int, float, None] = None,
    random_state: Union[int, RandomState, None] = None,
) -> Tuple[Dataset,Dataset, Dataset]:
    train, valid_test = split_w_stratify(ds, test_size=test_size)
    valid, test = split_w_stratify(valid_test, test_size=0.1)
    return train, valid, test

# %% ../nbs/00_core.ipynb 54
def prepare_dataset(ds):
    print("Preparing dataset...")
    print("dropping duplicates...")
    ds = filter_bad_images(ds)
    # ds = get_fpath(ds)
    # ds = drop_duplicates(ds)
    # print("getting ID...")
    # ds = ds.map(get_id)
    print("creating train, valid, test splits...")
    train, valid, test = train_valid_split_w_stratify(ds)
    data = {"train": train,
            "valid": valid,
            "test": test}
    for k,v  in data.items():
        print(f"{k} has {len(v)} examples")
    return train,valid,test

# %% ../nbs/00_core.ipynb 60
def prepare_transforms(model_checkpoint, train_ds, valid_ds, test_ds=None):
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_checkpoint)
    normalize = Normalize(mean=feature_extractor.image_mean, std=feature_extractor.image_std)
    _train_transforms = Compose(
            [
                Resize((feature_extractor.size,feature_extractor.size)),
                RandomAdjustSharpness(0.1),
                RandomAutocontrast(),
                ToTensor(),
                normalize,
                RandomErasing()
            ]
        )

    _val_transforms = Compose(
            [
                Resize((feature_extractor.size, feature_extractor.size)),
                ToTensor(),
                normalize,
            ]
        )

    def train_transforms(examples):
        examples['pixel_values'] = [_train_transforms(image.convert("RGB")) for image in examples['image']]
        return examples

    def val_transforms(examples):
        examples['pixel_values'] = [_val_transforms(image.convert("RGB")) for image in examples['image']]
        return examples
    if test_ds is not None:
        test_ds.set_transform(val_transforms)
    train_ds.set_transform(train_transforms)
    valid_ds.set_transform(val_transforms)
    return train_ds, valid_ds, test_ds

# %% ../nbs/00_core.ipynb 63
@dataclass
class FlyswotData:
    train_ds: datasets.arrow_dataset.Dataset
    valid_ds: datasets.arrow_dataset.Dataset
    test_ds: datasets.arrow_dataset.Dataset
    id2label: Dict[int,str]
    label2id: Dict[str,int]

# %% ../nbs/00_core.ipynb 64
def prep_data(ds, model_checkpoint=None):
    try:
        labels = ds.info.features['label'].names
        id2label = dict(enumerate(labels))
        label2id = {v:k for k,v in id2label.items()}
        train, valid, test = prepare_dataset(ds)
        train_ds, valid_ds, test_ds = prepare_transforms(model_checkpoint, train, valid, test)
        return FlyswotData(train_ds, valid_ds, test_ds, id2label, label2id)
    except FileNotFoundError as e:
        print(f"{e} make sure you are logged into the Hugging Face Hub")

# %% ../nbs/00_core.ipynb 72
def collate_fn(examples):
    pixel_values = torch.stack([example["pixel_values"] for example in examples])
    labels = torch.tensor([example["label"] for example in examples])
    return {"pixel_values": pixel_values, "labels": labels}

# %% ../nbs/00_core.ipynb 73
from sklearn.metrics import classification_report

# %% ../nbs/00_core.ipynb 74
def train_model(data, 
                model_checkpoint,
                num_epochs=50,
                hub_model_id="flyswot",
                tune=False,
               fp16=True):
    transformers.logging.set_verbosity_warning()
    train_ds, valid_ds, test_ds, id2label, label2id = asdict(data).values()
    print(train_ds)
    model = AutoModelForImageClassification.from_pretrained(model_checkpoint, num_labels=len(id2label),
                                                   id2label=id2label,
                                                  label2id=label2id, ignore_mismatched_sizes=True)
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_checkpoint)
    args = TrainingArguments(
    "output_dir",
    save_strategy="epoch",
    evaluation_strategy="epoch",
    hub_model_id=f"flyswot/{hub_model_id}",
    overwrite_output_dir=True,
    push_to_hub=True,
    learning_rate=2e-5,
    per_device_train_batch_size=4, 
    per_device_eval_batch_size=4,
    num_train_epochs=num_epochs,
    weight_decay=0.1,disable_tqdm=False,
    fp16=fp16,
   # load_best_model_at_end=True,
    #metric_for_best_model="f1",
    logging_dir='logs',
    remove_unused_columns=False,
    save_total_limit=10,
    optim="adamw_torch",
    seed=42,    
)
    def compute_metrics(eval_pred):
        precision_metric = load_metric("precision")
        recall_metric = load_metric("recall")
        f1_metric = load_metric("f1")
        accuracy_metric = load_metric("accuracy")

        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        precision = precision_metric.compute(predictions=predictions, references=labels,average='macro')["precision"]
        recall = recall_metric.compute(predictions=predictions, references=labels,average='macro')["recall"]
        f1 = f1_metric.compute(predictions=predictions, references=labels,average='macro')['f1']
        accuracy = accuracy_metric.compute(predictions=predictions, references=labels)['accuracy']
        return {"precision": precision, "recall": recall, "f1":f1, "accuracy":accuracy}

    
    # def compute_metrics(eval_pred):
    #     predictions, labels = eval_pred
    #     id2label = model.config.id2label
    #     predictions = np.argmax(predictions, axis=1)
    #     # report = classification_report(labels,
    #     #               predictions, output_dict=True,zero_division=0)
    #     # per_label = {} 
    #     # for k,v in report.items():
    #     #     if k.isdigit():
    #     #         label = id2label[int(k)]
    #     #         metrics = v['f1-score']
    #     #         per_label[f"{label}_f1"] = metrics  
    #     return f1.compute(predictions=predictions, references=labels, average='macro')


    trainer = Trainer(model,
                      args,
    train_dataset=train_ds,
    eval_dataset=valid_ds,
    data_collator=collate_fn,
    compute_metrics=compute_metrics,
    tokenizer=feature_extractor)
    trainer.train()
    return trainer

# %% ../nbs/00_core.ipynb 82
def plot_confusion_matrix(outputs, trainer):
    from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(15, 15))
    y_true = outputs.label_ids
    y_pred = outputs.predictions.argmax(1)
    labels =trainer.model.config.id2label.values()
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    disp.plot(xticks_rotation=45, ax=ax)


# %% ../nbs/00_core.ipynb 84
def create_classification_report(outputs, trainer):
    from sklearn.metrics import classification_report
    y_true = outputs.label_ids
    y_pred = outputs.predictions.argmax(1)
    labels =trainer.model.config.id2label.values()
    return classification_report(y_true, y_pred, target_names=labels, output_dict=True)

# %% ../nbs/00_core.ipynb 92
def create_test_results_df(outputs, trainer, important_label=None, print_results=True, return_df=False) -> pd.DataFrame:
    id2label = trainer.model.config.id2label
    y_true = outputs.label_ids
    y_pred = outputs.predictions.argmax(1)
    y_prob = softmax(outputs.predictions, axis=1)
   # ids = test_data['id']
    df = pd.DataFrame({"y_true":y_true,"y_pred": y_pred, "y_prob": y_prob.max(1)})
    df.y_true = df.y_true.map(id2label)
    df.y_pred = df.y_pred.map(id2label)
    if print_results:
        misclassified_df = df[df.y_true != df.y_pred]
        print('misclasified:')
        print(misclassified_df)
        print('\n')
        if important_label:
            print(f"Number of wrong predictions of {important_label} label: {len(misclassified_df[misclassified_df['y_pred']==important_label])}")
            print(f"Percentage of wrong predictions of {important_label} label: {(len(misclassified_df[misclassified_df['y_pred']==important_label])/len(df))*100}")
    if return_df:
        return df


# %% ../nbs/00_core.ipynb 97
def create_mistakes_image_navigator(test_results_df, flyswot_data,trainer):
    import panel as pn
    pn.extension()
    df = test_results_df
    mistakes = df.y_true!=df.y_pred
    mistake_ids = df.index[mistakes].tolist()
    df = df[mistakes]
    df = df.reset_index(drop=True)
    subset = flyswot_data.test_ds.select(mistake_ids)
    assert len(df) == len(subset)
    if len(df)<1:
        print(df)
        return subset['image'][0]
    index_selection = pn.widgets.DiscreteSlider(options=df.index.to_list())
    id2label = trainer.model.config.id2label
    @pn.depends(index_selection)
    def get_image(selection):
        image = subset[selection]['image']
        image = pn.Pane(image)
        #row = flyswot_data.test_ds[selection]
       # string_label = id2label[row['label']]
       # label =  pn.pane.Markdown(f"""actual label: **{string_label}**""")
        df_row = df.iloc[selection]
        r = pn.Row(image, pn.Pane(df_row))
        return r
    df = df.reset_index(drop=True)
    return pn.Column(index_selection,get_image)

# %% ../nbs/00_core.ipynb 103
def create_misclassified_report(outputs, trainer, test_data, important_label=None, print_results=True, return_df=False):
    id2label = trainer.model.config.id2label
    y_true = outputs.label_ids
    y_pred = outputs.predictions.argmax(1)
    y_prob = softmax(outputs.predictions, axis=1)
    df = pd.DataFrame({"y_true":y_true,"y_pred": y_pred, "y_prob": y_prob.max(1)})
    df.y_true = df.y_true.map(id2label)
    df.y_pred = df.y_pred.map(id2label)
    if print_results:
        misclassified_df = df[df.y_true != df.y_pred]
        print('misclasified:')
        print(misclassified_df)
        print('\n')
        if important_label:
            print(f"Number of wrong predictions of {important_label} label: {len(misclassified_df[misclassified_df['y_pred']==important_label])}")
            print(f"Percentage of wrong predictions of {important_label} label: {(len(misclassified_df[misclassified_df['y_pred']==important_label])/len(df))*100}")
    if return_df:
        return misclassified_df

