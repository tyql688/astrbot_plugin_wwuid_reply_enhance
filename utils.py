from typing import List, Tuple, Optional, Any, Dict
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
import astrbot.api.message_components as Comp

def extract_text_and_images_from_chain(chain: List[object]) -> Tuple[str, List[str]]:
    """递归从消息链中提取文本和图片URL"""
    texts: List[str] = []
    images: List[str] = []
    if not isinstance(chain, list):
        return "", images
        
    for seg in chain:
        try:
            if isinstance(seg, Comp.Plain):
                txt = getattr(seg, "text", None)
                if txt: texts.append(str(txt))
            elif isinstance(seg, Comp.Image):
                # 优先取 url，其次 file
                u = getattr(seg, "url", None) or getattr(seg, "file", None)
                if u: images.append(u)
            # 处理合并转发节点 (Node/Nodes/Forward)
            elif hasattr(Comp, "Node") and isinstance(seg, getattr(Comp, "Node")): # Node
                 t, i = extract_text_and_images_from_chain(getattr(seg, "content", []) or [])
                 if t: texts.append(t)
                 images.extend(i)
            elif hasattr(Comp, "Nodes") and isinstance(seg, getattr(Comp, "Nodes")): # Nodes
                nodes = getattr(seg, "nodes", []) or getattr(seg, "content", []) or []
                for node in nodes:
                    t, i = extract_text_and_images_from_chain(getattr(node, "content", []) or [])
                    if t: texts.append(t)
                    images.extend(i)
            elif hasattr(Comp, "Forward") and isinstance(seg, getattr(Comp, "Forward")): # Forward
                nodes = getattr(seg, "nodes", []) or getattr(seg, "content", []) or []
                for node in nodes:
                    t, i = extract_text_and_images_from_chain(getattr(node, "content", []) or [])
                    if t: texts.append(t)
                    images.extend(i)
        except Exception as e:
            continue
    return "\n".join(texts), images

def ob_data(obj: Any) -> Dict[str, Any]:
    """解包 OneBot data 字段"""
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
        return obj["data"]
    return obj if isinstance(obj, dict) else {}

def extract_from_onebot_payload(payload: Any) -> Tuple[str, List[str]]:
    """解析 OneBot 原始数据包"""
    texts, images = [], []
    data = ob_data(payload)
    
    # 兼容 message, messages, nodes 等字段
    msgs = data.get("message") or data.get("messages") or data.get("nodes")
    
    if isinstance(msgs, list):
        for item in msgs:
            # 递归处理 list 中的 dict
            if isinstance(item, dict):
                # 如果是节点(node)，内容通常在 content 或 message 中
                content = item.get("content") or item.get("message")
                if isinstance(content, list):
                    t, i = extract_from_onebot_payload({"message": content})
                    if t: texts.append(t)
                    images.extend(i)
                    continue
                
                # 处理基础消息段
                t = item.get("type")
                d = item.get("data", {})
                if t in ("text", "plain"):
                    texts.append(d.get("text", ""))
                elif t == "image":
                    images.append(d.get("url") or d.get("file"))
                elif t in ("forward", "nodes"): # 嵌套转发
                    # 这里通常只有一个 id，需要进一步 API 调用，暂忽略或仅记录 ID
                    pass
    elif isinstance(msgs, str):
        texts.append(msgs)
        
    return "\n".join(texts), images

async def extract_quoted_payload(event: AstrMessageEvent) -> List[str]:
    """
    增强版引用提取：
    1. 尝试从 event 自带的 Reply 组件提取
    2. 如果是 OneBot 且 Reply 组件信息不全（如合并转发），尝试调用 API 获取
    返回: 图片 URL 列表
    """
    # 1. 尝试直接解析消息链
    chain = []
    try:
        chain = event.get_messages()
    except:
        chain = getattr(event.message_obj, "message", [])

    reply_comp = next((x for x in chain if isinstance(x, Comp.Reply)), None)
    if not reply_comp:
        return []

    # 尝试从组件内直接获取
    for attr in ["content", "message", "origin"]:
        content = getattr(reply_comp, attr, None)
        if isinstance(content, list) and content:
            _, imgs = extract_text_and_images_from_chain(content)
            if imgs: return imgs

    # 2. 如果直接获取失败，且为 OneBot 协议，尝试 API 调用
    # 获取 reply_id
    reply_id = getattr(reply_comp, "id", None) or getattr(reply_comp, "message_id", None)
    if not reply_id and isinstance(getattr(reply_comp, "data", None), dict):
         reply_id = reply_comp.data.get("id")

    if reply_id and event.get_platform_name() == "aiocqhttp" and hasattr(event, "bot"):
        try:
            # 获取原消息
            ret = await event.bot.api.call_action("get_msg", message_id=str(reply_id))
            _, imgs = extract_from_onebot_payload(ret)
            
            # 检查是否包含 nested forward id，如果有需要再次 fetch (简易处理：检查 ret 数据结构)
            # 注意：如果 get_msg 返回的是合并转发（type: nodes），通常不包含直接图片，需要 get_forward_msg
            # 但 Napcat/LLOneBot 的 get_msg 对于转发消息通常返回 type: forward 和 resid
            data = ob_data(ret)
            msg_list = data.get("message", [])
            if isinstance(msg_list, list):
                for seg in msg_list:
                    if isinstance(seg, dict) and seg.get("type") == "forward":
                        fid = seg.get("data", {}).get("id")
                        if fid:
                            fwd_ret = await event.bot.api.call_action("get_forward_msg", id=fid)
                            _, fwd_imgs = extract_from_onebot_payload(fwd_ret)
                            imgs.extend(fwd_imgs)
            
            if imgs: return imgs
        except Exception as e:
            logger.warning(f"wwuid_reply_enhance API fetch failed: {e}")

    return []
