"""训练 Qwen3-0.6B 记忆路由 LoRA，并冻结可复现 manifest。"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path
from typing import Any

import torch
import yaml
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

from backend.training.memory_route.common import build_training_text, iter_jsonl, load_schema, validate_records


class RouteDataset(Dataset):
    """预编码 assistant-only loss 的路由训练样本。"""

    def __init__(self, tokenizer: Any, records: list[dict[str, Any]], max_length: int):
        """编码 prompt 与标签，并屏蔽 prompt token loss。"""
        self.examples: list[dict[str, list[int]]] = []
        for record in records:
            prompt, full_text = build_training_text(tokenizer, record)
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            encoded = tokenizer(full_text, add_special_tokens=False, truncation=True, max_length=max_length)
            input_ids = list(encoded["input_ids"])
            if len(prompt_ids) >= len(input_ids):
                raise ValueError(f"label_truncated:{record['sample_id']}")
            labels = [-100] * len(prompt_ids) + input_ids[len(prompt_ids) :]
            self.examples.append({"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels})

    def __len__(self) -> int:
        """返回编码样本数量。"""
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        """返回单条预编码样本。"""
        return self.examples[index]


class RouteCollator:
    """按批次右侧填充 input、mask 和 label。"""

    def __init__(self, pad_token_id: int):
        """保存 tokenizer pad token。"""
        self.pad_token_id = pad_token_id

    def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
        """构建不会让 padding 参与 loss 的张量批次。"""
        width = max(len(item["input_ids"]) for item in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for item in features:
            padding = width - len(item["input_ids"])
            batch["input_ids"].append(item["input_ids"] + [self.pad_token_id] * padding)
            batch["attention_mask"].append(item["attention_mask"] + [0] * padding)
            batch["labels"].append(item["labels"] + [-100] * padding)
        return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}


def _load_model(model_id: str, revision: str, quantization: str) -> Any:
    """按 BF16 或 NF4 方式加载底模。"""
    options: dict[str, Any] = {"revision": revision, "device_map": "cuda"}
    if quantization == "nf4":
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        options["dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(model_id, **options)
    if quantization == "nf4":
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    return model


def train(args: argparse.Namespace) -> dict[str, Any]:
    """执行校验、LoRA 训练、Adapter 保存和运行 manifest 冻结。"""
    records = list(iter_jsonl(args.dataset))
    validate_records(records, load_schema(args.schema), require_approved=not args.allow_unreviewed_smoke)
    train_records = [record for record in records if record["split"] == "train"]
    validation_records = [record for record in records if record["split"] == "validation"]
    if not train_records:
        raise ValueError("empty_train_split")
    torch.manual_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    model = _load_model(args.model_id, args.revision, args.quantization)
    model.config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.lora_rank,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    training = RouteDataset(tokenizer, train_records, args.max_length)
    validation = RouteDataset(tokenizer, validation_records, args.max_length) if validation_records else None
    started = time.perf_counter()
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.output / "checkpoints"),
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            learning_rate=args.learning_rate,
            num_train_epochs=args.epochs,
            max_steps=args.max_steps,
            logging_steps=1,
            save_strategy=args.save_strategy,
            eval_strategy="no" if validation is None else "epoch",
            bf16=True,
            gradient_checkpointing=True,
            report_to=[],
            seed=args.seed,
            data_seed=args.seed,
            remove_unused_columns=False,
        ),
        train_dataset=training,
        eval_dataset=validation,
        data_collator=RouteCollator(tokenizer.pad_token_id),
    )
    result = trainer.train()
    adapter_path = args.output / "adapter"
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    manifest = {
        "model_id": args.model_id,
        "revision": args.revision,
        "tokenizer_revision": args.revision,
        "quantization": args.quantization,
        "python": platform.python_version(),
        "torch": str(torch.__version__),
        "cuda_runtime": str(torch.version.cuda),
        "gpu": torch.cuda.get_device_name(0),
        "seed": args.seed,
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
        "max_steps": args.max_steps,
        "save_strategy": args.save_strategy,
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "train_samples": len(training),
        "validation_samples": len(validation) if validation else 0,
        "train_loss": float(result.training_loss),
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1048576, 1),
        "review_bypass": bool(args.allow_unreviewed_smoke),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "run_manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest


def main() -> None:
    """解析稳定训练参数并启动训练。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("dataset_schema.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen3-0.6B")
    parser.add_argument("--revision", default="c1899de289a04d12100db370d81485cdf75e47ca")
    parser.add_argument("--quantization", choices=("bf16", "nf4"), default="nf4")
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--save-strategy", choices=("no", "epoch"), default="no")
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--allow-unreviewed-smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(train(args), ensure_ascii=False))


if __name__ == "__main__":
    main()
