import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import torch

import comfy.model_management
import comfy.utils
from comfy_api.input_impl import VideoFromFile
import folder_paths

from .client import GrsaiClient, image_payload, video_payload, job_identity
from .prompts import outfit_prompt, text_prompt, video_prompt


CATEGORY = '我的工具箱/线上模型'
SIZES = ['941x1672', '1024x1024', '1672x941', '1024x1536', '1090x1443', '1120x1408', 'auto']
JOB_HELP = '任务编号已自动生成，无需修改。旧工作流中的编号也不影响自动识别；更换素材或参数会自动新建任务。'
BATCH_INPUT = ('INT', {'default': 0, 'min': 0, 'max': 2147483647,
    'tooltip': '通常保持0。相同素材和参数想再生成一版时加1；相同批次重跑会复用结果或续查。'})


def encode_image(tensor):
    pixels = (tensor[0].detach().cpu().numpy().clip(0, 1) * 255).round().astype(np.uint8)
    image = Image.fromarray(pixels).convert('RGB')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def decode_image(path):
    with Image.open(path) as image:
        pixels = np.array(ImageOps.exif_transpose(image).convert('RGB'), dtype=np.float32) / 255
    return torch.from_numpy(pixels).unsqueeze(0)


def run_cloud(kind, task_name, payload, generation=0):
    progress = comfy.utils.ProgressBar(100)
    client = GrsaiClient(Path(folder_paths.get_output_directory()) / '线上工具箱' / '任务记录')
    return client.run(kind, task_name, payload,
                      generation=generation,
                      check_interrupt=comfy.model_management.throw_exception_if_processing_interrupted,
                      on_progress=lambda value: progress.update_absolute(value, 100))


class CloudFashionTextToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'prompt': ('STRING', {'multiline': True, 'default': '写实成年女性服装模特，灰色走廊，自然微笑，穿黑白千鸟格上衣和棕色A字裙，光线自然。', 'tooltip': '填写人物、服装、场景或任何想生成的画面。'}),
            'size': (SIZES, {'default': '941x1672', 'tooltip': '请求的图片尺寸；实际尺寸以中转站返回为准。'}),
            'full_outfit': ('BOOLEAN', {'default': True, 'label_on': '完整露脸和整套服装', 'label_off': '自由构图', 'tooltip': '服装模特建议开启；风景等非人物画面可关闭。'}),
            'task_name': ('STRING', {'default': '自动', 'tooltip': JOB_HELP}),
        }, 'optional': {'重新生成批次': BATCH_INPUT}}

    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('生成图片', '任务状态')
    FUNCTION = 'generate'
    CATEGORY = CATEGORY

    def generate(self, prompt, size, full_outfit, task_name, 重新生成批次=0):
        payload = image_payload(text_prompt(prompt, full_outfit), size, [])
        path, task_id = run_cloud('text_image', task_name, payload, 重新生成批次)
        name = job_identity('text_image', payload, 重新生成批次)[0]
        return decode_image(path), f'gpt-image-2.5 | {name} | 任务 {task_id} | 相同内容自动复用或续查'


class CloudFashionOutfit:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'person': ('IMAGE', {'tooltip': '唯一的人物身份图，脸清楚、身体比例完整。'}),
            'garment': ('IMAGE', {'tooltip': '目标衣服图：平铺、挂拍、穿在别人身上的衣服均可。'}),
            'instructions': ('STRING', {'multiline': True, 'default': '自然贴合人物，忠实保留衣服的版型、花纹和装饰。', 'tooltip': '写明要替换上衣、裙子或整套服装，以及其他要求。'}),
            'size': (SIZES, {'default': '941x1672'}),
            'full_outfit': ('BOOLEAN', {'default': True, 'label_on': '完整露脸和整套服装', 'label_off': '沿用参考构图'}),
            'task_name': ('STRING', {'default': '自动', 'tooltip': JOB_HELP}),
        }, 'optional': {
            '重新生成批次': BATCH_INPUT,
            'bottom': ('IMAGE', {'tooltip': '可选的独立裙子或裤子图；连接后 garment 用作上衣，bottom 用作下装。'}),
            'pose': ('IMAGE', {'tooltip': '可选姿势参考图，只参考肢体姿势，不替换人物身份。'}),
        }}

    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('换装图片', '任务状态')
    FUNCTION = 'generate'
    CATEGORY = CATEGORY

    def generate(self, person, garment, instructions, size, full_outfit, task_name, bottom=None, pose=None, 重新生成批次=0):
        images = [encode_image(person), encode_image(garment)]
        if bottom is not None:
            images.append(encode_image(bottom))
        if pose is not None:
            images.append(encode_image(pose))
        prompt = outfit_prompt(instructions, full_outfit, bottom is not None, pose is not None)
        payload = image_payload(prompt, size, images)
        path, task_id = run_cloud('outfit_image', task_name, payload, 重新生成批次)
        name = job_identity('outfit_image', payload, 重新生成批次)[0]
        return decode_image(path), f'gpt-image-2.5 | {name} | 任务 {task_id} | 换装图片可接入线上视频'


class CloudFashionImageToVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'image': ('IMAGE', {'tooltip': '已经确认的换装图或人物图；建议完整露脸、上衣和整个裙摆都可见。'}),
            'keywords': ('STRING', {'multiline': True, 'default': '服装模特展示：正面站姿，轻侧身扶胯，轻展裙摆，回正微笑；动作舒缓，重点展示衣服。'}),
            'resolution': (['480p', '768p', '1080p'], {'default': '1080p'}),
            'duration': ('INT', {'default': 10, 'min': 1, 'max': 15, 'step': 1, 'tooltip': '1080P最多10秒；480P/768P最多15秒。'}),
            'orientation': (['portrait', 'landscape'], {'default': 'portrait'}),
            'full_outfit': ('BOOLEAN', {'default': True, 'label_on': '全程完整露脸和衣裙', 'label_off': '自由构图'}),
            'seed': ('INT', {'default': 2026101304, 'min': 0, 'max': 2147483647}),
            'task_name': ('STRING', {'default': '自动', 'tooltip': JOB_HELP}),
        }, 'optional': {
            '重新生成批次': BATCH_INPUT,
            'pose': ('IMAGE', {'tooltip': '可选的造型参考图；模特自然过渡到该姿势，人物和服装仍来自主图。'}),
        }}

    RETURN_TYPES = ('VIDEO', 'STRING')
    RETURN_NAMES = ('生成视频', '任务状态')
    FUNCTION = 'generate'
    CATEGORY = CATEGORY

    def generate(self, image, keywords, resolution, duration, orientation, full_outfit, seed, task_name, pose=None, 重新生成批次=0):
        images = [encode_image(image)]
        if pose is not None:
            images.append(encode_image(pose))
        prompt = video_prompt(keywords, duration, full_outfit, pose is not None)
        payload = video_payload(prompt, resolution, duration, orientation, seed, images)
        path, task_id = run_cloud('video', task_name, payload, 重新生成批次)
        name = job_identity('video', payload, 重新生成批次)[0]
        return VideoFromFile(str(path)), f'minimax-h3 | {name} | {resolution} | 请求 {duration}秒 | 任务 {task_id} | 实际尺寸和时长以返回文件为准'


NODE_CLASS_MAPPINGS = {
    'CloudFashionTextToImage': CloudFashionTextToImage,
    'CloudFashionOutfit': CloudFashionOutfit,
    'CloudFashionImageToVideo': CloudFashionImageToVideo,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'CloudFashionTextToImage': '01 线上文生图 · GPT Image 2.5',
    'CloudFashionOutfit': '02 线上人物换装 · GPT Image 2.5',
    'CloudFashionImageToVideo': '03 线上图生视频 · MiniMax H3',
}
