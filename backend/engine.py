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
            cls._instance._loading = False
            cls._instance._ready = False
            cls._instance._error = None
            print(f"ModelEngine (ZImage) initialized. Device: {DEVICE}")
            # 不再自动加载，由 worker 在后台线程加载
        return cls._instance

    def is_ready(self) -> bool:
        """检查模型是否已就绪"""
        return self._ready and self.pipe is not None

    def is_loading(self) -> bool:
        """检查模型是否正在加载"""
        return self._loading

    def get_error(self) -> str | None:
        """获取加载错误信息"""
        return self._error

    def load_model(self):
        """同步加载模型（在后台线程中调用）"""
        if self.pipe is not None:
            self._ready = True
            return

        if self._loading:
            return  # 已经在加载中

        self._loading = True
        self._error = None

        if DEVICE != "cuda":
            error_msg = "ZImage FP8 模型当前仅支持在 CUDA 设备上运行，请确保有可用 GPU。"
            self._error = error_msg
            self._loading = False
            raise RuntimeError(error_msg)

        print("[Engine] 正在加载 FP8 Transformer...")
        try:
            transformer = ZImageTransformer2DModel.from_pretrained(
                MODEL_PATH,
                subfolder="transformer",
                torch_dtype=torch.float8_e4m3fn,  # 关键：FP8
                low_cpu_mem_usage=False,
            )

            print("[Engine] 正在组装 ZImagePipeline...")
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
            self._ready = True
            self._loading = False
            print("[Engine] ZImage 模型加载完成。")
        except Exception as e:
            error_msg = f"加载 ZImage 模型失败: {e}"
            self._error = error_msg
            self._loading = False
            print(f"[Engine] {error_msg}")
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
        if not self.is_ready():
            if self._error:
                raise RuntimeError(f"模型未就绪: {self._error}")
            elif self._loading:
                raise RuntimeError("模型正在加载中，请稍候...")
            else:
                raise RuntimeError("模型未加载，请先加载模型")

        #print(f"Generating with ZImage: {prompt}")

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
