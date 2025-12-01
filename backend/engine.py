import os
import uuid

import torch
from diffusers import ZImagePipeline

# 根据 config.json 确定的类名
try:
    from diffusers import ZImageTransformer2DModel
except ImportError as e:
    # 如果这里失败，整个后端最好直接报错退出，而不是悄悄继续
    print("错误：无法导入 ZImageTransformer2DModel。请确认 diffusers 版本支持该类。")
    raise e


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR = os.path.dirname(__file__)

# 使用 Hugging Face Hub 的模型 ID（走默认的 ~/.cache/huggingface）
# TODO: 把下面这行改成你实际使用的 ZImage 模型 ID，例如：
# MODEL_ID = "ZhipuAI/zimage-1.0-dev0"
MODEL_ID = "Tongyi-MAI/Z-Image-Turbo"
MODEL_PATH = MODEL_ID


class ModelEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelEngine, cls).__new__(cls)
            cls._instance.pipe = None
            print(f"ModelEngine (ZImage) initialized. Device: {DEVICE}")
            cls._instance.load_model()
        return cls._instance

    def load_model(self):
        if self.pipe is not None:
            return

        if DEVICE != "cuda":
            raise RuntimeError("ZImage FP8 模型当前仅支持在 CUDA 设备上运行，请确保有可用 GPU。")

        print("正在加载 FP8 Transformer...")
        try:
            transformer = ZImageTransformer2DModel.from_pretrained(
                MODEL_PATH,
                subfolder="transformer",
                torch_dtype=torch.float8_e4m3fn,  # 关键：FP8
                low_cpu_mem_usage=False,
            )

            print("正在组装 ZImagePipeline...")
            pipe = ZImagePipeline.from_pretrained(
                MODEL_PATH,
                transformer=transformer,
                torch_dtype=torch.bfloat16,  # 其他部分使用 BF16
                low_cpu_mem_usage=False,
            )

            pipe.to(DEVICE)
            # 强烈建议：开启 CPU Offload，减少显存占用
            pipe.enable_model_cpu_offload()

            self.pipe = pipe
            print("ZImage 模型加载完成。")
        except Exception as e:
            print(f"加载 ZImage 模型失败: {e}")
            raise

    def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        steps: int = 20,
        width: int = 512,
        height: int = 512,
        cfg_scale: float = 7.5,
    ) -> str:
        """生成图片并返回保存的文件名（与原有接口保持一致）。"""
        if self.pipe is None:
            self.load_model()

        print(f"Generating with ZImage: {prompt}")

        # 使用传入参数，如果不想要引导可设置 cfg_scale=0.0
        generator = torch.Generator(DEVICE).manual_seed(42)

        # 有的 ZImage 版本暂时不支持 negative_prompt，可按需删掉该参数
        kwargs = dict(
            prompt=prompt,
            height=height,
            width=width,
            num_inference_steps=steps,
            guidance_scale=cfg_scale,
            generator=generator,
        )
        if negative_prompt is not None:
            kwargs["negative_prompt"] = negative_prompt

        image = self.pipe(**kwargs).images[0]

        # 保存为 webp，路径和返回值格式与之前保持一致
        output_dir = os.path.join(BASE_DIR, "generated_images")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.webp"
        filepath = os.path.join(output_dir, filename)
        image.save(filepath, format="WEBP", quality=90)

        print(f"Saved to {filepath}")
        return filename


engine = ModelEngine()
