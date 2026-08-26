import copy
import os

from loguru import logger

from llmc.utils import deploy_all_modality

# Lazy imports for eval classes
_eval_classes = {}

def _get_eval_class(name):
    """Lazy load eval classes to avoid importing heavy dependencies."""
    if name not in _eval_classes:
        if name == 'AccuracyEval':
            from llmc.eval.eval_acc import AccuracyEval
            _eval_classes[name] = AccuracyEval
        elif name == 'PerplexityEval':
            from llmc.eval.eval_ppl import PerplexityEval
            _eval_classes[name] = PerplexityEval
        elif name == 'DecodePerplexityEval':
            from llmc.eval.eval_ppl import DecodePerplexityEval
            _eval_classes[name] = DecodePerplexityEval
        elif name == 'TokenConsistencyEval':
            from llmc.eval.eval_token_consist import TokenConsistencyEval
            _eval_classes[name] = TokenConsistencyEval
        elif name == 'VQAEval':
            from llmc.eval.eval_vqa import VQAEval
            _eval_classes[name] = VQAEval
        elif name == 'HumanEval':
            from llmc.eval.eval_code import HumanEval
            _eval_classes[name] = HumanEval
        elif name == 'CustomGenerate':
            from llmc.eval.eval_custom_generate import CustomGenerate
            _eval_classes[name] = CustomGenerate
        elif name == 'CustomGenerateJustInfer':
            from llmc.eval.eval_custom_generate_just_infer import CustomGenerateJustInfer
            _eval_classes[name] = CustomGenerateJustInfer
        elif name == 'VideoGenerateEval':
            from llmc.eval.eval_video_generate import VideoGenerateEval
            _eval_classes[name] = VideoGenerateEval
        else:
            raise ValueError(f'Unknown eval class: {name}')
    return _eval_classes[name]


def get_eval_list(model, config):
    eval_list = []
    if int(os.environ['RANK']) == 0:
        if 'eval' in config:
            if 'type' in config.eval and config.eval.type == 'decode_ppl':
                if 'pretrain' in config.eval.eval_pos:
                    raise ValueError(
                        'Unsupported: Evaluating decode_ppl with a pretrained model. '
                    )
                    # Pretrained models do not use key-value caching.
                    # Please use a transformed model to evaluate decode_ppl
                    # for the original model.

            if not isinstance(config.eval, list):
                eval_config_list = [config.eval]
            else:
                eval_config_list = config.eval
            for eval_config in eval_config_list:
                config_tmp = copy.deepcopy(config)
                config_tmp.eval = eval_config
                if 'type' not in config_tmp.eval:
                    config_tmp.eval['type'] = 'ppl'
                if 'eval' in config_tmp and len(config_tmp.eval.eval_pos):
                    name_list = (
                        config_tmp.eval.name
                        if not isinstance(config_tmp.eval.name, str)
                        else [config_tmp.eval.name]
                    )
                    for name in name_list:
                        config_for_eval = copy.deepcopy(config_tmp)
                        config_for_eval.eval.name = name
                        if len(name_list) != 1:  # eval multi datasets
                            config_for_eval.eval.path = os.path.join(
                                config_tmp.eval.path, name
                            )
                        if 'type' not in config_tmp.eval:
                            config_tmp.eval.type == 'ppl'
                        if config_tmp.eval.type == 'acc':
                            AccuracyEval = _get_eval_class('AccuracyEval')
                            eval_class = AccuracyEval(config_for_eval)
                        elif config_tmp.eval.type == 'vqa':
                            VQAEval = _get_eval_class('VQAEval')
                            eval_class = VQAEval(config_for_eval)
                        elif (
                            config_tmp.eval.type == 'code'
                            and config_tmp.eval.name == 'human_eval'
                        ):
                            HumanEval = _get_eval_class('HumanEval')
                            eval_class = HumanEval(model, config_for_eval)
                        elif config_tmp.eval.type == 'generate_only':
                            CustomGenerate = _get_eval_class('CustomGenerate')
                            eval_class = CustomGenerate(model, config_for_eval)
                        elif config_tmp.eval.type == 'just_infer':
                            CustomGenerateJustInfer = _get_eval_class('CustomGenerateJustInfer')
                            eval_class = CustomGenerateJustInfer(model, config_for_eval)
                        elif config_tmp.eval.type == 'token_acc':
                            TokenConsistencyEval = _get_eval_class('TokenConsistencyEval')
                            eval_class = TokenConsistencyEval(model, config_for_eval)
                        elif config_tmp.eval.type == 'ppl':
                            PerplexityEval = _get_eval_class('PerplexityEval')
                            eval_class = PerplexityEval(model, config_for_eval)
                        elif config_tmp.eval.type == 'decode_ppl':
                            DecodePerplexityEval = _get_eval_class('DecodePerplexityEval')
                            eval_class = DecodePerplexityEval(model, config_for_eval)
                        elif config_tmp.eval.type == 'video_gen':
                            VideoGenerateEval = _get_eval_class('VideoGenerateEval')
                            eval_class = VideoGenerateEval(model, config_for_eval)
                        else:
                            raise ValueError(
                                f'Unsupported eval type: {config_tmp.eval.type}'
                            )
                        eval_list.append((eval_class, config_for_eval))
    return eval_list


def eval_model(model, blockwise_opts, eval_list, eval_pos):
    if int(os.environ['RANK']) == 0:
        do_eval = False
        for _, config_for_eval in eval_list:
            if eval_pos in config_for_eval.eval.eval_pos:
                do_eval = True
        if do_eval:
            if eval_pos == 'transformed':
                deploy_all_modality(blockwise_opts, 'origin_float')
            elif eval_pos in ['fake_quant', 'fake_quant_wo_kv']:
                deploy_all_modality(blockwise_opts, 'fake_quant')
            for eval_class, config_for_eval in eval_list:
                if eval_pos in config_for_eval.eval.eval_pos:
                    res = eval_class.eval(model, eval_pos)
                    eval_name = config_for_eval.eval.type
                    dataset_name = config_for_eval.eval.name
                    logger.info(f'EVAL: {eval_name} on {dataset_name} is {res}')
