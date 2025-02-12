from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
import os

class NLPProcessor:
    def __init__(self):
        # If a fine-tuned model exists, load it; otherwise load the base model.
        fine_tuned_dir = "app/models/fine_tuned_model"
        if os.path.exists(fine_tuned_dir):
            self.model = AutoModelForSequenceClassification.from_pretrained(fine_tuned_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(fine_tuned_dir)
        else:
            self.model = AutoModelForSequenceClassification.from_pretrained("cointegrated/rubert-tiny-toxicity")
            self.tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny-toxicity")
        self.model.eval()
        
    async def analyze(self, text: str) -> bool:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs, return_dict=True)
        probabilities = torch.sigmoid(outputs.logits).tolist()[0]
        toxicity_score = probabilities[0] if probabilities else 0.0
        threshold = 0.7
        return toxicity_score >= threshold
