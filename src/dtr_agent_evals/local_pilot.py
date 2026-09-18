"""Real local Ollama pilot, bounded to JSON integer answers and exact validation.

No generated code, shell command, URL, or tool invocation is ever executed.
Checkpoint feedback can affect later output, so each regime is run end to end.
"""
import hashlib,json,platform,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import numpy as np

SCHEMA={"type":"object","properties":{"answer":{"type":"integer"}},"required":["answer"],"additionalProperties":False}
REASONING_SCHEMA={"type":"object","properties":{"reasoning":{"type":"string"},"answer":{"type":"integer"}},"required":["reasoning","answer"],"additionalProperties":False}
REASONING_SYSTEM='You are an arithmetic agent. Calculate carefully, showing intermediate computations in the reasoning string before giving the final integer answer. Return JSON with exactly two fields: reasoning (string) and answer (integer). Do not write code.'
SYSTEM='You are an arithmetic agent. Follow the task and checkpoint feedback carefully. Return only JSON with one integer field "answer". No prose. No code.'


def api(base,path,payload=None,timeout=180):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(base+path,data=data,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)


def parse_answer(content, allow_reasoning=None):
    try:
        val=json.loads(content)
        expected={"reasoning","answer"} if allow_reasoning else {"answer"}
        if allow_reasoning is not None and (not isinstance(val,dict) or set(val)!=expected):return None
        if isinstance(val,dict) and set(val) in ({"answer"},{"reasoning","answer"}) and type(val["answer"]) is int and ("reasoning" not in val or isinstance(val["reasoning"],str)):return val["answer"]
    except (ValueError,TypeError):pass
    return None


def task_from_seed(seed, family="modular"):
    if family == "small_products":
        rng=np.random.default_rng(seed)
        a,c=map(int,rng.integers(11,30,size=2));b,d=map(int,rng.integers(2,10,size=2));e=int(rng.integers(10,50))
        return {"seed":seed,"a":a,"b":b,"c":c,"d":d,"e":e,"expression":f"({a} * {b}) + ({c} * {d}) - {e}","answer":a*b+c*d-e}
    if family != "modular":raise ValueError(family)
    rng=np.random.default_rng(seed)
    a,b,c,d=map(int,rng.integers(11,80,size=4));e=int(rng.integers(50,400));m=int(rng.choice([47,59,71,83,97]))
    expression=f"(({a} * {b}) + ({c} * {d}) - {e}) mod {m}"
    return {"seed":seed,"a":a,"b":b,"c":c,"d":d,"e":e,"m":m,"expression":expression,"answer":((a*b)+(c*d)-e)%m}


def action_probability(regime,t,last_correct):
    if regime=="logging":return .5 if t==0 else (.25 if last_correct else .75)
    if regime=="always_small":return 0.
    if regime=="always_large":return 1.
    if regime=="fixed_switch":return float(t>=1)
    if regime=="failure_escalation":return float(t>0 and not last_correct)
    raise ValueError(regime)


def run_trajectory(cfg,task,regime,episode,model_digests):
    seed=cfg["seed"]+episode*1009
    rng=np.random.default_rng(seed)
    reasoning=cfg.get("allow_reasoning",False);family=cfg.get("task_family","modular")
    final_quantity="remainder" if family=="modular" else "integer answer"
    if reasoning:
        instruction=f"Compute {task['expression']}. First compute each multiplication, then add the products, then subtract. Show intermediate arithmetic in the reasoning string and put the exact final integer in answer."
    else:
        # Preserve the original two pilot prompts byte-for-byte for reproducibility.
        instruction=f"Compute {task['expression']}. Here mod means the nonnegative integer remainder. Give the exact final {final_quantity} as JSON: {{\"answer\": integer}}."
    messages=[{"role":"system","content":REASONING_SYSTEM if reasoning else SYSTEM},{"role":"user","content":instruction}]
    events=[];correct=None
    for t in range(cfg["horizon"]):
        p=action_probability(regime,t,correct);a=int(rng.binomial(1,p));model=cfg["models"][a]
        model_seed=seed+t;start=time.perf_counter()
        request={"model":model,"messages":messages,"stream":False,"format":REASONING_SCHEMA if reasoning else SCHEMA,
          "options":{"seed":model_seed,"temperature":cfg["temperature"],"num_predict":cfg["num_predict"],"num_ctx":2048},"keep_alive":"30m"}
        response=api(cfg["ollama_url"],"/api/chat",request)
        elapsed=time.perf_counter()-start;content=response["message"]["content"];answer=parse_answer(content,allow_reasoning=reasoning)
        prior_correct=correct;correct=answer==task["answer"]
        terminal=t==cfg["horizon"]-1
        # Unitless prespecified resource proxy, not billed dollars or energy.
        proxy=cfg["resource_cost"][a]
        reward=float(correct) if terminal else 0.
        event={"episode_id":episode,"regime":regime,"task_id":f"arithmetic-{task['seed']}","task_seed":task["seed"],
          "stage":t,"previous_correct":prior_correct,"action":a,"model":model,"model_digest":model_digests[model],
          "probability_large":p,"observed_action_probability":p if a else 1-p,"rng_seed":seed,"model_seed":model_seed,
          "messages":json.loads(json.dumps(messages)),"response":content,"parsed_answer":answer,"correct":correct,
          "terminal":terminal,"reward":reward,"resource_proxy":proxy,"utility_increment":reward-proxy,
          "wall_seconds":elapsed,"eval_count":response.get("eval_count"),"prompt_eval_count":response.get("prompt_eval_count"),
          "eval_duration_ns":response.get("eval_duration"),"prompt_eval_duration_ns":response.get("prompt_eval_duration"),
          "load_duration_ns":response.get("load_duration"),"total_duration_ns":response.get("total_duration"),
          "done_reason":response.get("done_reason"),"created_at":response.get("created_at"),"request_sha256":hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()}
        events.append(event);messages.append({"role":"assistant","content":content})
        if not terminal:
            if correct:feedback=f"The deterministic validator reports that the previous answer is correct. Verify your answer and return the same exact final {final_quantity}."
            else:
                hint=f"{task['a']} * {task['b']} = {task['a']*task['b']}" if t==0 else f"{task['c']} * {task['d']} = {task['c']*task['d']}"
                feedback=f"The deterministic validator reports that the previous answer is incorrect. A trusted arithmetic tool supplies this partial result: {hint}. Recompute the original full expression and return its exact final {final_quantity}."
            messages.append({"role":"user","content":feedback})
    summary={"episode_id":episode,"task_id":f"arithmetic-{task['seed']}","regime":regime,
       "final_success":int(correct),"utility":sum(e["utility_increment"] for e in events),
       "resource_proxy":sum(e["resource_proxy"] for e in events),"wall_seconds":sum(e["wall_seconds"] for e in events),
       "generated_tokens":sum(e["eval_count"] or 0 for e in events),"actions":[e["action"] for e in events],
       "correctness":[e["correct"] for e in events],"switched":int(any(events[t]["action"]!=events[t-1]["action"] for t in range(1,len(events))))}
    return events,summary


def run(cfg,out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):raise FileExistsError(f"Refusing to overwrite nonempty result directory: {out}")
    out.mkdir(parents=True,exist_ok=True)
    tags=api(cfg["ollama_url"],"/api/tags");lookup={m["name"]:m for m in tags["models"]}
    model_digests={name:lookup[name]["digest"] for name in cfg["models"]}
    if cfg.get("expected_digests") and model_digests != cfg["expected_digests"]:
        raise RuntimeError("Model manifest digests differ from the prespecified pinned models")
    metadata={m:api(cfg["ollama_url"],"/api/show",{"model":m}) for m in cfg["models"]}
    manifest={"started_at":datetime.now(timezone.utc).isoformat(),"config":cfg,"model_digests":model_digests,
      "model_metadata":metadata,"ollama_version":api(cfg["ollama_url"],"/api/version"),"platform":platform.platform(),
      "machine":platform.machine(),"system_prompt":REASONING_SYSTEM if cfg.get("allow_reasoning") else SYSTEM,"schema":REASONING_SCHEMA if cfg.get("allow_reasoning") else SCHEMA,
      "license_sources":["https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/LICENSE","https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE"],
      "provenance_note":"Ollama registry manifest/content digests pin actual quantized artifacts. Upstream Hugging Face commit was not asserted to be recoverable from Ollama metadata."}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    episodes=[];tasks=[];episode=0
    with (out/"events.jsonl").open("w") as events_file,(out/"episodes.jsonl").open("w") as episode_file:
        for split,n in (("logging",cfg["logging_tasks"]),("heldout",cfg["heldout_tasks"])):
            for i in range(n):
                task_seed=cfg["seed"]+(0 if split=="logging" else 100000)+i
                task=task_from_seed(task_seed,cfg.get("task_family","modular"));tasks.append({**task,"split":split})
                regimes=["logging"] if split=="logging" else cfg["evaluation_regimes"]
                # Reverse alternate task blocks to reduce fixed order latency artifacts.
                if i%2:regimes=list(reversed(regimes))
                for regime in regimes:
                    ev,ep=run_trajectory(cfg,task,regime,episode,model_digests)
                    for e in ev:events_file.write(json.dumps(e)+"\n")
                    events_file.flush();episode_file.write(json.dumps(ep)+"\n");episode_file.flush()
                    episodes.append(ep);episode+=1
                print(f"{split}: completed {i+1}/{n} tasks, {episode} trajectories",flush=True)
    (out/"tasks.json").write_text(json.dumps(tasks,indent=2)+"\n")
    manifest["completed_at"]=datetime.now(timezone.utc).isoformat();manifest["episodes"]=len(episodes)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return episodes
