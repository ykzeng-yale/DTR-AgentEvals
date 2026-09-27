---
base_model: Kwai-Klear/Klear-AgentForge-8B
language:
- en
library_name: transformers
license: apache-2.0
mradermacher:
  readme_rev: 1
quantized_by: mradermacher
---
## About

<!-- ### quantize_version: 2 -->
<!-- ### output_tensor_quantised: 1 -->
<!-- ### convert_type: hf -->
<!-- ### vocab_type:  -->
<!-- ### tags:  -->
<!-- ### quants:  x-f16 Q4_K_S Q2_K Q8_0 Q6_K Q3_K_M Q3_K_S Q3_K_L Q4_K_M Q5_K_S Q5_K_M IQ4_XS -->
<!-- ### quants_skip:  -->
<!-- ### skip_mmproj:  -->
static quants of https://huggingface.co/Kwai-Klear/Klear-AgentForge-8B

<!-- provided-files -->

***For a convenient overview and download list, visit our [model page for this model](https://hf.tst.eu/model#Klear-AgentForge-8B-GGUF).***

weighted/imatrix quants seem not to be available (by me) at this time. If they do not show up a week or so after the static ones, I have probably not planned for them. Feel free to request them by opening a Community Discussion.
## Usage

If you are unsure how to use GGUF files, refer to one of [TheBloke's
READMEs](https://huggingface.co/TheBloke/KafkaLM-70B-German-V0.1-GGUF) for
more details, including on how to concatenate multi-part files.

## Provided Quants

(sorted by size, not necessarily quality. IQ-quants are often preferable over similar sized non-IQ quants)

| Link | Type | Size/GB | Notes |
|:-----|:-----|--------:|:------|
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q2_K.gguf) | Q2_K | 3.4 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q3_K_S.gguf) | Q3_K_S | 3.9 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q3_K_M.gguf) | Q3_K_M | 4.2 | lower quality |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q3_K_L.gguf) | Q3_K_L | 4.5 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.IQ4_XS.gguf) | IQ4_XS | 4.7 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q4_K_S.gguf) | Q4_K_S | 4.9 | fast, recommended |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q4_K_M.gguf) | Q4_K_M | 5.1 | fast, recommended |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q5_K_S.gguf) | Q5_K_S | 5.8 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q5_K_M.gguf) | Q5_K_M | 6.0 |  |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q6_K.gguf) | Q6_K | 6.8 | very good quality |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.Q8_0.gguf) | Q8_0 | 8.8 | fast, best quality |
| [GGUF](https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/main/Klear-AgentForge-8B.f16.gguf) | f16 | 16.5 | 16 bpw, overkill |

Here is a handy graph by ikawrakow comparing some lower-quality quant
types (lower is better):

![image.png](https://www.nethype.de/huggingface_embed/quantpplgraph.png)

And here are Artefact2's thoughts on the matter:
https://gist.github.com/Artefact2/b5f810600771265fc1e39442288e8ec9

## FAQ / Model Request

See https://huggingface.co/mradermacher/model_requests for some answers to
questions you might have and/or if you want some other model quantized.

## Thanks

I thank my company, [nethype GmbH](https://www.nethype.de/), for letting
me use its servers and providing upgrades to my workstation to enable
this work in my free time.

<!-- end -->
