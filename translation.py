import logging
import os

import torch

from core import encoder_mask, decoder_mask
from core import traindataloader

logfilepath = ""  # 따로 지정하지 않으면 terminal에 뜸
if os.path.isfile(logfilepath):
    os.remove(logfilepath)
logging.basicConfig(filename=logfilepath, level=logging.INFO)

def greedy_decode(net, src, src_mask, START_INDEX=2, END_INDEX=3, PADDING_INDEX=1):

    # encoder 추론
    for encoder in net.Encoders:
        from_encoder = encoder(src, src_mask)

    # Inference의 경우 decoder에는 일단 START_INDEX로 구성된 sequence 한개의 배열만 넣는다.
    tgt = torch.ones(1, 1).fill_(START_INDEX).type_as(src)
    for i in range(src.shape[-1]-1):
        tgt_mask = decoder_mask(tgt, padding_index=PADDING_INDEX)

        # decoder 추론
        for decoder in net.Decoders:
            output = decoder(tgt, from_encoder, src_mask, tgt_mask)
        output = torch.softmax(net.output(output), dim=-1)

        # 행에서 가장 아래의 것(결과 or 현재)만 가져온다.
        prediction = net.output(output[:, -1]) # 맨 위에것을 가져온다. (1, tgt_vocab_size)
        _, next_word = torch.max(prediction, dim=-1) # max, max_indices 반환
        next_word = next_word.item()

        # 행 방향으로 결과를 쌓는다. -> 다시 decoder의 입력이 된다.
        tgt = torch.cat([tgt, torch.ones(1, 1).fill_(next_word).type_as(src)], dim=-1)

        # end index를 만나면 for문을 벗어난다.
        if next_word == END_INDEX:
            break

    return tgt

def translate(net: torch.nn.Module, src_sentence: str, device: object):

    _, dataset = traindataloader()
    src = dataset.sequential_transform[dataset.SRC_LANGUAGE](src_sentence).view(1, -1).to(device) # (batch, sequence length)
    src_mask = encoder_mask(src, padding_index=dataset.PAD_IDX) # 마스크 생성

    tgt_tokens = greedy_decode(
        net,  src, src_mask,
        START_INDEX=dataset.BOS_IDX,
        END_INDEX=dataset.EOS_IDX,
        PADDING_INDEX=dataset.PAD_IDX).flatten()

    start_token = dataset.special_symbols[-2] # '<bos>'
    enc_token = dataset.special_symbols[-1] # '<eos>'
    # torchtext 매우 유용하다
    return " ".join(dataset.vocab_transform[dataset.TGT_LANGUAGE].lookup_tokens(list(tgt_tokens.cpu().numpy()))).replace(start_token, "").replace(enc_token, "")

if __name__ == "__main__":

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    if torch.cuda.device_count() > 0 :
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    logging.info("jit model test")
    weight_path = os.path.join("weights", "transformer")
    try:
        net = torch.jit.load(os.path.join(weight_path, "0100.jit"), map_location=device)
        net.eval()
    except Exception:
        # DEBUG, INFO, WARNING, ERROR, CRITICAL 의 5가지 등급
        logging.info("loading jit 실패")
        exit(0)
    else:
        logging.info("loading jit 성공")

    # 번역 시작
    translate(net, "Eine Gruppe von Menschen steht vor einem Iglu .", device)
    # result :
    translate(net, "Ich leite ein Unternehmen.", device)
    # result :