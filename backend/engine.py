import torch
from diffusers import StableDiffusionPipeline
import os
import uuid

# Configure device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = "prompthero/openjourney"

class ModelEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelEngine, cls).__new__(cls)
            cls._instance.pipe = None
            print(f"ModelEngine initialized. Device: {DEVICE}")
            # Eager loading or lazy loading based on preference
            cls._instance.load_model() 
        return cls._instance

    def load_model(self):
        if self.pipe is None:
            print(f"Loading model {MODEL_ID}...")
            try:
                self.pipe = StableDiffusionPipeline.from_pretrained(
                    MODEL_ID, 
                    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32
                )
                self.pipe.to(DEVICE)
                print("Model loaded successfully.")
            except Exception as e:
                print(f"Error loading model: {e}")
                raise e

    def generate(self, prompt: str, negative_prompt: str = None, steps: int = 20, width: int = 512, height: int = 512, cfg_scale: float = 7.5) -> str:
        if self.pipe is None:
            self.load_model()

        print(f"Generating: {prompt}")
        
        # Run generation
        # OpenJourney often works better with slightly different default params, but standard call is fine
        # The user's prompt example suggests adding style keywords if not present
        final_prompt = prompt
        if "mdjrny-v4 style" not in final_prompt:
             final_prompt = f"{final_prompt}, mdjrny-v4 style"
             
        image = self.pipe(
            prompt=final_prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=steps,
            width=width,
            height=height,
            guidance_scale=cfg_scale,
        ).images[0]

        # Save image
        output_dir = "generated_images"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.webp"
        filepath = os.path.join(output_dir, filename)
        image.save(filepath, format="WEBP", quality=90)
        
        print(f"Saved to {filepath}")
        return filename

engine = ModelEngine()
