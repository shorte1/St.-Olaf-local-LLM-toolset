import subprocess
import requests
import json
import time
import csv
import os
import threading
from datetime import datetime

OLLAMA_URL = "http://localhost:11435"
TESTS_DIR = os.path.expanduser("~/llm-test/benchmark/tests")
RESULTS_DIR = os.path.expanduser("~/llm-test/benchmark/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

MODELS = [
    "deepseek-r1:7b",
    "deepseek-r1:32b",
    "llama3.2:3b",
    "llama3.2:8b",
    "qwen2.5:7b",
    "mistral:7b",
    "qwen2.5:32b",
    "gemma2:27b",
    "mistral-small:22b",
]

def get_gpu_stats():
    try:
        result = subprocess.run([
            'nvidia-smi',
            '--query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw',
            '--format=csv,noheader,nounits',
            '-i', '0,1'  # explicitly target both GPUs
        ], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        stats = []
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            stats.append({
                'gpu_id': int(parts[0]),
                'util': float(parts[1]),
                'mem_used': float(parts[2]),
                'mem_total': float(parts[3]),
                'power': float(parts[4])
            })
        return stats
    except Exception as e:
        print(f"GPU stats error: {e}")
        return []

def sample_gpu_during_inference(stop_event, samples):
    while not stop_event.is_set():
        stats = get_gpu_stats()
        if stats:
            samples.append(stats)
        time.sleep(0.1)  # changed from 0.5 to 0.1 (100ms)

def pull_model(model):
    print(f"  Checking if {model} is available...")
    result = subprocess.run(
        ['podman', 'exec', 'ollama-internal', 'ollama', 'list'],
        capture_output=True, text=True
    )
    if model in result.stdout:
        print(f"  {model} already available")
        return True
    
    print(f"  Pulling {model}...")
    result = subprocess.run(
        ['podman', 'exec', 'ollama-internal', 'ollama', 'pull', model],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Failed to pull {model}: {result.stderr}")
        return False
    print(f"  {model} pulled successfully")
    return True

def run_prompt(model, prompt):
    url = f"{OLLAMA_URL}/api/generate"
    
    # Start GPU sampling in background
    stop_event = threading.Event()
    gpu_samples = []
    gpu_thread = threading.Thread(
        target=sample_gpu_during_inference,
        args=(stop_event, gpu_samples)
    )
    gpu_thread.start()

    start_time = time.time()
    first_token_time = None
    full_response = ""
    token_count = 0

    try:
        response = requests.post(url,
            json={"model": model, "prompt": prompt},
            stream=True,
            timeout=300
        )

        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get('response', '')
                if token and first_token_time is None:
                    first_token_time = time.time()
                full_response += token
                token_count += 1

    except Exception as e:
        full_response = f"ERROR: {e}"
    finally:
        stop_event.set()
        gpu_thread.join()

    end_time = time.time()
    total_time = end_time - start_time
    time_to_first_token = (first_token_time - start_time) if first_token_time else None
    tokens_per_second = token_count / total_time if total_time > 0 else 0

    # Average GPU stats across samples for each GPU
    avg_gpu0_util = 0
    avg_gpu1_util = 0
    avg_gpu0_mem = 0
    avg_gpu1_mem = 0
    avg_power = 0

    if gpu_samples:
        gpu0_samples = [s for sample in gpu_samples for s in sample if s['gpu_id'] == 0]
        gpu1_samples = [s for sample in gpu_samples for s in sample if s['gpu_id'] == 1]

        if gpu0_samples:
            avg_gpu0_util = sum(s['util'] for s in gpu0_samples) / len(gpu0_samples)
            avg_gpu0_mem = sum(s['mem_used'] for s in gpu0_samples) / len(gpu0_samples)
        if gpu1_samples:
            avg_gpu1_util = sum(s['util'] for s in gpu1_samples) / len(gpu1_samples)
            avg_gpu1_mem = sum(s['mem_used'] for s in gpu1_samples) / len(gpu1_samples)
        
        all_samples = [s for sample in gpu_samples for s in sample]
        avg_power = sum(s['power'] for s in all_samples) / len(all_samples)

    return {
        'total_time': round(total_time, 2),
        'time_to_first_token': round(time_to_first_token, 2) if time_to_first_token else None,
        'tokens_per_second': round(tokens_per_second, 2),
        'token_count': token_count,
        'avg_gpu0_util': round(avg_gpu0_util, 1),
        'avg_gpu1_util': round(avg_gpu1_util, 1),
        'avg_gpu0_mem_mb': round(avg_gpu0_mem, 0),
        'avg_gpu1_mem_mb': round(avg_gpu1_mem, 0),
        'avg_power_w': round(avg_power, 1),
        'response': full_response
    }

def load_prompts(category):
    filepath = os.path.join(TESTS_DIR, f"{category}.txt")
    with open(filepath, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def run_benchmark(models=None, categories=None):
    if models is None:
        models = MODELS
    if categories is None:
        categories = ['reasoning', 'coding', 'knowledge', 'instruction', 'context']

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = os.path.join(RESULTS_DIR, f"benchmark_{timestamp}.csv")
    report_path = os.path.join(RESULTS_DIR, f"benchmark_{timestamp}.txt")
    responses_dir = os.path.join(RESULTS_DIR, f"responses_{timestamp}")
    os.makedirs(responses_dir, exist_ok=True)

    csv_rows = []
    report_lines = []

    report_lines.append(f"LLM Benchmark Report")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Models tested: {', '.join(models)}")
    report_lines.append("=" * 80)

    for model in models:
        print(f"\nTesting model: {model}")
        report_lines.append(f"\nModel: {model}")
        report_lines.append("-" * 40)

        if not pull_model(model):
            print(f"Skipping {model} - could not pull")
            continue

        for category in categories:
            print(f"  Category: {category}")
            prompts = load_prompts(category)

            for i, prompt in enumerate(prompts):
                print(f"    Prompt {i+1}/{len(prompts)}...", end='', flush=True)
                
                result = run_prompt(model, prompt)
                
                print(f" done ({result['total_time']}s, {result['tokens_per_second']} tok/s)")

                # Save response to file for manual review
                response_file = os.path.join(
                    responses_dir,
                    f"{model.replace(':', '_')}_{category}_{i+1}.txt"
                )
                with open(response_file, 'w') as f:
                    f.write(f"Model: {model}\n")
                    f.write(f"Category: {category}\n")
                    f.write(f"Prompt: {prompt}\n")
                    f.write("=" * 40 + "\n")
                    f.write(result['response'])

                # Add to CSV data
                csv_rows.append({
                    'model': model,
                    'category': category,
                    'prompt_num': i + 1,
                    'prompt': prompt[:100] + '...' if len(prompt) > 100 else prompt,
                    'total_time_s': result['total_time'],
                    'time_to_first_token_s': result['time_to_first_token'],
                    'tokens_per_second': result['tokens_per_second'],
                    'token_count': result['token_count'],
                    'avg_gpu0_util_pct': result['avg_gpu0_util'],
                    'avg_gpu1_util_pct': result['avg_gpu1_util'],
                    'avg_gpu0_mem_mb': result['avg_gpu0_mem_mb'],
                    'avg_gpu1_mem_mb': result['avg_gpu1_mem_mb'],
                    'avg_power_w': result['avg_power_w'],
                })

                # Add to report
                report_lines.append(f"\n  [{category}] Prompt {i+1}: {prompt[:60]}...")
                report_lines.append(f"    Total time:          {result['total_time']}s")
                report_lines.append(f"    Time to first token: {result['time_to_first_token']}s")
                report_lines.append(f"    Tokens per second:   {result['tokens_per_second']}")
                report_lines.append(f"    Token count:         {result['token_count']}")
                report_lines.append(f"    Avg GPU0 util:       {result['avg_gpu0_util']}%")
                report_lines.append(f"    Avg GPU1 util:       {result['avg_gpu1_util']}%")
                report_lines.append(f"    Avg GPU0 VRAM:       {result['avg_gpu0_mem_mb']}MB")
                report_lines.append(f"    Avg GPU1 VRAM:       {result['avg_gpu1_mem_mb']}MB")
                report_lines.append(f"    Avg power draw:      {result['avg_power_w']}W")

    # Write CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
        writer.writeheader()
        writer.writerows(csv_rows)

    # Write report
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"\nBenchmark complete!")
    print(f"CSV results:  {csv_path}")
    print(f"Text report:  {report_path}")
    print(f"Responses:    {responses_dir}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LLM Benchmark Tool')
    parser.add_argument('--models', nargs='+', help='Models to test', default=None)
    parser.add_argument('--categories', nargs='+', help='Test categories to run', default=None)
    args = parser.parse_args()
    run_benchmark(models=args.models, categories=args.categories)
