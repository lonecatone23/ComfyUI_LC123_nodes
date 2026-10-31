"""
Anima LoRAs in Diffusers names
------------------------------
ComfyUI reads Anima LoRAs saved with the model's own names (blocks.0.self_attn.q_proj) and Kohya's lora_unet_ form,
but not ones saved with Diffusers names (transformer_blocks.0.attn1.to_q, ff.net.0.proj, text_conditioner ...): every
key is reported "not loaded" and the LoRA does nothing. This adds the Diffusers names (with the usual transformer. /
base_model.model. / lora_transformer_ prefixes) as extra entries in ComfyUI's LoRA key map for Anima and Cosmos
Predict2 models, so the stock LoRA loaders, LC LoRA Loader and the ModelBuilder LoRA tools all read them. Existing
entries are never replaced; other models are not touched. Name table after HaDeS Anima Suite (Devildonia, MIT).
"""

import comfy.lora

# the model's own name -> the Diffusers name, applied in order to the path inside diffusion_model.
_TO_DIFFUSERS = (
    (".self_attn.q_proj", ".attn1.to_q"),
    (".self_attn.k_proj", ".attn1.to_k"),
    (".self_attn.v_proj", ".attn1.to_v"),
    (".self_attn.output_proj", ".attn1.to_out.0"),
    (".self_attn.q_norm", ".attn1.norm_q"),
    (".self_attn.k_norm", ".attn1.norm_k"),
    (".cross_attn.q_proj", ".attn2.to_q"),
    (".cross_attn.k_proj", ".attn2.to_k"),
    (".cross_attn.v_proj", ".attn2.to_v"),
    (".cross_attn.output_proj", ".attn2.to_out.0"),
    (".cross_attn.q_norm", ".attn2.norm_q"),
    (".cross_attn.k_norm", ".attn2.norm_k"),
    (".mlp.layer1", ".ff.net.0.proj"),
    (".mlp.layer2", ".ff.net.2"),
    (".adaln_modulation_self_attn.1", ".norm1.linear_1"),
    (".adaln_modulation_self_attn.2", ".norm1.linear_2"),
    (".adaln_modulation_cross_attn.1", ".norm2.linear_1"),
    (".adaln_modulation_cross_attn.2", ".norm2.linear_2"),
    (".adaln_modulation_mlp.1", ".norm3.linear_1"),
    (".adaln_modulation_mlp.2", ".norm3.linear_2"),
)
_PREFIXES = (
    ("blocks.", "transformer_blocks."),
    ("t_embedder.1.linear_1", "time_embed.emb.timestep_embedder.linear_1"),
    ("t_embedder.1.linear_2", "time_embed.emb.timestep_embedder.linear_2"),
    ("t_embedding_norm", "time_embed.norm"),
    ("x_embedder.proj.1", "patch_embed.proj"),
    ("final_layer.linear", "proj_out"),
    ("final_layer.adaln_modulation.1", "norm_out.linear_1"),
    ("final_layer.adaln_modulation.2", "norm_out.linear_2"),
    ("llm_adapter.", "text_conditioner."),
)


def _diffusers_name(path):
    for own, diff in _PREFIXES:
        if path.startswith(own):
            path = diff + path[len(own):]
            break
    for own, diff in _TO_DIFFUSERS:
        path = path.replace(own, diff)
    return path


def _is_anima(model):
    import comfy.model_base

    kinds = tuple(getattr(comfy.model_base, n) for n in ("Anima", "CosmosPredict2") if hasattr(comfy.model_base, n))
    return bool(kinds) and isinstance(model, kinds)


def _add_aliases(model, key_map):
    for k in model.state_dict().keys():
        if not (k.startswith("diffusion_model.") and k.endswith(".weight")):
            continue
        path = k[len("diffusion_model."):-len(".weight")]
        d = _diffusers_name(path)
        if d == path:
            continue
        for alias in (d, "transformer." + d, "diffusion_model." + d, "base_model.model.transformer." + d,
                      "base_model.model." + d, "lora_transformer_" + d.replace(".", "_"), "lora_unet_" + d.replace(".", "_")):
            key_map.setdefault(alias, k)


def _install():
    orig = comfy.lora.model_lora_keys_unet
    if getattr(orig, "_lc_anima", False):
        return

    def model_lora_keys_unet(model, key_map={}):
        key_map = orig(model, key_map)
        try:
            if _is_anima(model):
                _add_aliases(model, key_map)
        except Exception as e:
            print(f"[LC123] Anima LoRA names: {e}")
        return key_map

    model_lora_keys_unet._lc_anima = True
    comfy.lora.model_lora_keys_unet = model_lora_keys_unet


_install()
