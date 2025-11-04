# fast_pipeline.py
"""
Fast parallel processing pipeline for VPS deployment
Optimized for speed and low resource usage
"""

from fast_road_classifier import FastRoadClassifier
from kml_camera_client import KMLCameraClient
from pathlib import Path
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class FastClassificationPipeline:
    """
    Optimized pipeline for VPS:
    - Parallel downloads
    - Fast lightweight classifier
    - No segmentation
    - Smart filtering
    """

    def __init__(self, output_dir="data/fast_classified", min_hazard_confidence=0.5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.camera_client = KMLCameraClient()
        self.classifier = FastRoadClassifier()

        self.results = {}
        self.lock = threading.Lock()
        self.min_hazard_confidence = min_hazard_confidence

    def setup(self, model_type='fast'):
        """Initialize classifier"""
        print("="*70)
        print("Fast Classification Pipeline Setup (VPS Optimized)")
        print("="*70)

        print("\nLoading fast classifier...")
        if not self.classifier.load_model(model_type):
            return False

        print("\n✓ Setup complete")
        return True

    def filter_major_highways(self, cameras):
        """
        Filter to major highways only (faster, more relevant)
        Focuses on I-15, I-80, I-70, US-89, etc.
        """
        major_roads = ['i-15', 'i-80', 'i-70', 'i-84', 'us-89', 'us-6', 'sr-']

        filtered = []
        for cam in cameras:
            name = cam.get('display_name', '').lower()
            if any(road in name for road in major_roads):
                filtered.append(cam)

        return filtered

    def process_single_camera(self, camera):
        """Process one camera (designed for parallel execution)"""
        cam_id = camera['id']

        try:
            # Download image
            image_path = self.camera_client.download_image(camera, str(self.output_dir))

            if not image_path:
                return {
                    'id': cam_id,
                    'camera': camera,
                    'status': 'download_failed',
                    'classification': None
                }

            # Classify
            classification = self.classifier.classify_road_condition(str(image_path))

            if classification:
                # Use configured confidence threshold
                safety_level, confidence = self.classifier.get_safety_level(
                    classification,
                    min_hazard_confidence=self.min_hazard_confidence
                )

                return {
                    'id': cam_id,
                    'camera': camera,
                    'status': 'success',
                    'classification': {
                        'condition': classification[0]['label'],
                        'confidence': classification[0]['score'],
                        'safety_level': safety_level,
                        'all_results': classification[:3],
                        'timestamp': datetime.now().isoformat()
                    },
                    'image_path': str(image_path)
                }
            else:
                return {
                    'id': cam_id,
                    'camera': camera,
                    'status': 'classification_failed',
                    'classification': None
                }

        except Exception as e:
            return {
                'id': cam_id,
                'camera': camera,
                'status': 'error',
                'classification': None,
                'error': str(e)
            }

    def process_cameras_parallel(self, cameras, max_workers=4, resume=True):
        """
        Process multiple cameras in parallel

        Args:
            cameras: List of cameras to process
            max_workers: Number of parallel workers (2-4 recommended for VPS)
            resume: Skip already processed cameras
        """
        # Load existing results if resuming
        results_file = self.output_dir / 'classification_results.json'
        if resume and results_file.exists():
            with open(results_file, 'r') as f:
                self.results = json.load(f)
            print(f"Loaded {len(self.results)} existing results")

        # Filter already processed
        if resume:
            cameras = [
                cam for cam in cameras
                if cam['id'] not in self.results or self.results[cam['id']]['status'] != 'success'
            ]
            print(f"Processing {len(cameras)} cameras (skipping already done)")

        if not cameras:
            print("All cameras already processed!")
            return self.results

        total = len(cameras)
        completed = 0
        start_time = time.time()

        print(f"\n🚀 Starting parallel processing with {max_workers} workers...")
        print(f"Total cameras: {total}")

        # Process in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_camera = {
                executor.submit(self.process_single_camera, cam): cam
                for cam in cameras
            }

            # Collect results as they complete
            for future in as_completed(future_to_camera):
                camera = future_to_camera[future]

                try:
                    result = future.result()

                    # Store result
                    with self.lock:
                        self.results[result['id']] = result
                        completed += 1

                    # Progress update
                    pct = (completed / total) * 100
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta_sec = (total - completed) / rate if rate > 0 else 0

                    status_emoji = {
                        'success': '✓',
                        'download_failed': '✗',
                        'classification_failed': '✗',
                        'error': '✗'
                    }.get(result['status'], '?')

                    print(f"[{completed}/{total}] {status_emoji} {camera.get('display_name', '')[:50]:50s} "
                          f"| {pct:5.1f}% | ETA: {eta_sec/60:4.1f}min | {rate:.1f} cam/sec")

                    # Periodic save
                    if completed % 20 == 0:
                        with self.lock:
                            with open(results_file, 'w') as f:
                                json.dump(self.results, f, indent=2)
                        print(f"  💾 Checkpoint saved ({completed}/{total})")

                except Exception as e:
                    print(f"✗ Error processing {camera.get('id')}: {e}")

        # Final save
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        elapsed_total = time.time() - start_time
        print(f"\n✓ All cameras processed!")
        print(f"  Total time: {elapsed_total/60:.1f} minutes")
        print(f"  Average: {elapsed_total/total:.1f} seconds/camera")
        print(f"  Throughput: {total/elapsed_total:.1f} cameras/second")

        return self.results


def main():
    """Run fast pipeline"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fast classification pipeline (VPS optimized)',
        epilog='Examples:\n'
               '  Test (20 cams):     python %(prog)s --max-cameras 20\n'
               '  Major highways:     python %(prog)s --max-cameras 500 --highways-only\n'
               '  All cameras:        python %(prog)s --max-cameras 900 --workers 4\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--max-cameras', type=int, default=100,
                       help='Maximum cameras to process (default: 100)')
    parser.add_argument('--workers', type=int, default=4,
                       help='Parallel workers (2-8, default: 4)')
    parser.add_argument('--highways-only', action='store_true',
                       help='Only process major highways (faster, more relevant)')
    parser.add_argument('--model', choices=['fast', 'balanced', 'accurate'], default='fast',
                       help='Model size (fast=CPU friendly, accurate=needs GPU)')
    parser.add_argument('--output-dir', type=str, default='data/fast_classified',
                       help='Output directory')
    parser.add_argument('--no-resume', action='store_true',
                       help='Start fresh')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='Minimum confidence for hazardous classification (default: 0.5)')

    args = parser.parse_args()

    # Create pipeline with confidence threshold
    pipeline = FastClassificationPipeline(
        output_dir=args.output_dir,
        min_hazard_confidence=args.min_confidence
    )

    if args.min_confidence != 0.5:
        print(f"\n💡 Using {args.min_confidence*100:.0f}% confidence threshold for hazardous classification")

    # Setup
    if not pipeline.setup(model_type=args.model):
        print("Setup failed")
        return

    # Fetch cameras
    print("\n" + "="*70)
    print("Fetching Cameras")
    print("="*70)

    all_cameras = pipeline.camera_client.fetch_cameras_from_kml(include_all=True)

    # Filter
    working_cameras = [
        cam for cam in all_cameras
        if cam.get('is_online') and cam.get('is_media_ready') and cam.get('image_url')
    ]

    print(f"Total online cameras: {len(working_cameras)}")

    # Filter to highways if requested
    if args.highways_only:
        working_cameras = pipeline.filter_major_highways(working_cameras)
        print(f"Major highways only: {len(working_cameras)}")

    # Limit
    cameras_to_process = working_cameras[:args.max_cameras]
    print(f"Will process: {len(cameras_to_process)}")

    # Estimate
    est_time_fast = len(cameras_to_process) * 1.5 / args.workers / 60  # Parallel time
    print(f"\nEstimated time: {est_time_fast:.1f} minutes")
    print(f"(With {args.workers} parallel workers)")

    if len(cameras_to_process) > 200:
        print(f"\n⚠️  Processing {len(cameras_to_process)} cameras")

    input("\nPress Enter to start or Ctrl+C to cancel...")

    # Process
    results = pipeline.process_cameras_parallel(
        cameras_to_process,
        max_workers=args.workers,
        resume=not args.no_resume
    )

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    stats = {
        'safe': sum(1 for r in results.values() if r.get('classification', {}).get('safety_level') == 'safe'),
        'caution': sum(1 for r in results.values() if r.get('classification', {}).get('safety_level') == 'caution'),
        'hazardous': sum(1 for r in results.values() if r.get('classification', {}).get('safety_level') == 'hazardous'),
        'failed': sum(1 for r in results.values() if r['status'] != 'success')
    }

    print(f"🟢 Safe: {stats['safe']}")
    print(f"🟡 Caution: {stats['caution']}")
    print(f"🔴 Hazardous: {stats['hazardous']}")
    print(f"✗ Failed: {stats['failed']}")

    print(f"\n✓ Results saved to: {args.output_dir}/classification_results.json")
    print(f"\nTo create map:")
    print(f"  python advanced_road_map.py --results {args.output_dir}/classification_results.json")


if __name__ == "__main__":
    main()
