import spaces
import gradio as gr
import json
import os
import tempfile
import time
from pathlib import Path

import torch
from transformers import Sam3Model, Sam3Processor
from mask_io import parse_boxes, export_masks

MODEL_ID = "facebook/sam3"
MODEL_REVISION = "3c879f39826c281e95690f02c7821c4de09afae7"
OUTPUT_ROOT = Path(tempfile.gettempdir()) / "scene-mask-results"
# ZeroGPU emulates CUDA at startup and materializes it inside the GPU callback.
model = Sam3Model.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                 token=os.environ.get("HF_TOKEN"), dtype=torch.bfloat16).to("cuda").eval()
processor = Sam3Processor.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                         token=os.environ.get("HF_TOKEN"))


@spaces.GPU(duration=45)
def infer(image, text, boxes, labels, confidence, mask_threshold):
    start = time.perf_counter()
    kwargs = {"images": image, "return_tensors": "pt"}
    if text:
        kwargs["text"] = text
    if boxes:
        kwargs["input_boxes"] = [boxes]
        kwargs["input_boxes_labels"] = [labels]
    inputs = processor(**kwargs).to("cuda")
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        outputs = model(**inputs)
    result = processor.post_process_instance_segmentation(
        outputs, threshold=confidence, mask_threshold=mask_threshold,
        target_sizes=inputs["original_sizes"].tolist())[0]
    return result["masks"].bool().cpu().numpy(), result["scores"].float().cpu().tolist(), time.perf_counter() - start


def segment(image, text, boxes_json, confidence, mask_threshold):
    if image is None:
        raise gr.Error("Upload an image first.")
    if image.width * image.height > 4_194_304:
        raise gr.Error("Use an image with at most 4 megapixels.")
    text = (text or "").strip()
    if len(text) > 200:
        raise gr.Error("Use an object description of at most 200 characters.")
    try:
        boxes, labels = parse_boxes(boxes_json, image.size)
    except (ValueError, TypeError) as error:
        raise gr.Error(str(error)) from None
    if not text and 1 not in labels:
        raise gr.Error("Describe an object or add an include box.")
    if not (0 <= confidence <= 1 and 0 <= mask_threshold <= 1):
        raise gr.Error("Thresholds must be between 0 and 1.")
    image = image.convert("RGB")
    masks, scores, seconds = infer(image, text, boxes, labels, confidence, mask_threshold)
    return export_masks(image, masks, scores, {
        "model": MODEL_ID, "model_revision": MODEL_REVISION, "text": text,
        "boxes": boxes, "box_labels": labels, "confidence_threshold": confidence,
        "mask_threshold": mask_threshold, "inference_seconds": seconds,
    }, OUTPUT_ROOT)


def select_corner(image, boxes_json, previous, mode, event: gr.SelectData):
    if image is None:
        return boxes_json, None, "Upload an image first."
    point = list(event.index)
    if previous is None:
        return boxes_json, point, "First corner selected. Click the opposite corner."
    x1, x2 = sorted([previous[0], point[0]])
    y1, y2 = sorted([previous[1], point[1]])
    try:
        boxes, labels = parse_boxes(boxes_json, image.size)
        values = [box + [label] for box, label in zip(boxes, labels)]
        values.append([x1, y1, x2, y2, 1 if mode == "Include" else 0])
        parse_boxes(json.dumps(values), image.size)
    except ValueError as error:
        return boxes_json, None, str(error)
    return json.dumps(values), None, "Box added. Select two more corners or run segmentation."


with gr.Blocks(title="Scene masks", delete_cache=(3600, 3600)) as demo:
    gr.Markdown("# Scene masks\nSelect an object, inspect its boundary, download the mask. The original pixels stay unchanged.")
    with gr.Row():
        with gr.Column():
            source = gr.Image(type="pil", image_mode="RGB", label="Source image", sources=["upload"])
            prompt = gr.Textbox(label="Object description", placeholder="tree")
            mode = gr.Radio(["Include", "Exclude"], value="Include", label="Box selection")
            hint = gr.Markdown("Optional: click two opposite corners around an object.")
            boxes = gr.Textbox(value="[]", label="Boxes in original image pixels", info="[x1, y1, x2, y2, label]; 1 includes, 0 excludes.")
            clear = gr.Button("Clear boxes")
            corner = gr.State(None)
            with gr.Accordion("Thresholds", open=False):
                confidence = gr.Slider(0, 1, value=0.5, step=0.01, label="Detection confidence")
                mask_threshold = gr.Slider(0, 1, value=0.5, step=0.01, label="Mask threshold")
            run = gr.Button("Create masks", variant="primary")
        with gr.Column():
            gallery = gr.Gallery(label="Candidate boundaries", columns=1, format="png")
            files = gr.Files(label="Native masks, source-pixel cutouts and record")
            record = gr.JSON(label="Result details")
    source.select(select_corner, [source, boxes, corner, mode], [boxes, corner, hint], api_name=False)
    source.upload(lambda: ("[]", None, "Click two opposite corners."), outputs=[boxes, corner, hint], api_name=False)
    clear.click(lambda: ("[]", None, "Click two opposite corners."), outputs=[boxes, corner, hint], api_name=False)
    run.click(segment, [source, prompt, boxes, confidence, mask_threshold], [gallery, files, record],
              api_name="segment", concurrency_limit=1)

if __name__ == "__main__":
    demo.queue(max_size=8).launch(show_error=False, max_file_size="20mb")
