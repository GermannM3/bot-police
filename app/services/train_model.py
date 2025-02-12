"""
This script demonstrates an offline fine-tuning pipeline for our toxicity classifier.
It reads training data from "training_data.json", where messages flagged by the bot and
admin feedback (like/dislike) are stored. The script converts the feedback into labels:
    - "like" means the flag was correct (user appeared intoxicated) → label 1.
    - "dislike" means the flag was incorrect (user was normal) → label 0.
The pipeline uses these labeled examples to fine-tune the model.
A scheduled training run (e.g., nightly) followed by a bot restart will reload the model,
gradually improving its discriminative capability.
Note: In production, you might want to add further data validation, error handling,
and use a proper machine learning pipeline.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

import torch
from torch.utils.data import Dataset

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRAINING_DATA_FILE = "training_data.json"
MODEL_SAVE_DIR = "app/models/fine_tuned_model"
MODEL_NAME = "cointegrated/rubert-tiny-toxicity"

class FeedbackDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: val.squeeze(0) for key, val in encoding.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item

def load_training_data(filepath):
    """
    Load training data from a JSON file.
    Only messages with non-null feedback are used.
    "like" indicates a correct flag (label 1) and "dislike" indicates an incorrect flag (label 0).
    """
    if not os.path.exists(filepath):
        logger.error(f"Training data file {filepath} does not exist.")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    examples = []
    for entry in data:
        feedback = entry.get("feedback")
        text = entry.get("text")
        # Only use examples where a feedback is given and text exists.
        if feedback is None or text is None:
            continue
        if feedback.lower() == "like":
            label = 1
        elif feedback.lower() == "dislike":
            label = 0
        else:
            continue
        examples.append({
            "text": text,
            "label": label,
            "timestamp": entry.get("timestamp", "")
        })
    logger.info(f"Loaded {len(examples)} examples from training data.")
    return examples

def main():
    examples = load_training_data(TRAINING_DATA_FILE)
    if not examples:
        logger.error("No training examples available. Exiting training pipeline.")
        return

    texts = [ex["text"] for ex in examples]
    labels = [ex["label"] for ex in examples]

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    dataset = FeedbackDataset(texts, labels, tokenizer)

    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=3,
        per_device_train_batch_size=8,
        learning_rate=2e-5,
        weight_decay=0.01,
        logging_steps=10,
        logging_dir="./logs",
        save_steps=50,
        save_total_limit=2,
        remove_unused_columns=False,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    logger.info("Starting fine-tuning process...")
    trainer.train()
    logger.info("Training complete.")

    Path(MODEL_SAVE_DIR).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MODEL_SAVE_DIR)
    tokenizer.save_pretrained(MODEL_SAVE_DIR)
    logger.info(f"Fine-tuned model saved to {MODEL_SAVE_DIR}")

if __name__ == "__main__":
    main()
