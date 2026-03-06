import tensorflow as tf
import torch
import sys
import os

def verify_gpu():
    print("="*50)
    print("🚀 NVIDIA GPU VERIFICATION 🚀")
    print("="*50)

    # 1. System Info
    print(f"\n[System Info]")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"CUDA_PATH: {os.environ.get('CUDA_PATH', 'Not Set')}")

    # 2. TensorFlow Verification
    print(f"\n[TensorFlow Verification]")
    print(f"Version: {tf.__version__}")
    tf_gpus = tf.config.list_physical_devices('GPU')
    if tf_gpus:
        print(f"✅ GPU Detected: {tf_gpus}")
        for gpu in tf_gpus:
            try:
                # Try a small operation to confirm it actually works
                with tf.device('/GPU:0'):
                    a = tf.constant([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
                    b = tf.constant([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
                    c = tf.matmul(a, b)
                print(f"✅ Matrix multiplication on GPU: SUCCESS")
            except Exception as e:
                print(f"❌ Operation failed: {e}")
    else:
        print("❌ No GPU found by TensorFlow.")

    # 3. PyTorch Verification
    print(f"\n[PyTorch Verification]")
    print(f"Version: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"✅ GPU Detected: Yes")
        print(f"✅ Device Name: {torch.cuda.get_device_name(0)}")
        print(f"✅ CUDA Version (PyTorch Build): {torch.version.cuda}")
        
        try:
            # Try a small operation
            x = torch.rand(5, 3).cuda()
            print(f"✅ Tensor creation on GPU: SUCCESS")
        except Exception as e:
            print(f"❌ Operation failed: {e}")
    else:
        print("❌ No GPU found by PyTorch.")

    print("\n" + "="*50)
    if tf_gpus and torch.cuda.is_available():
        print("🎉 CONGRATULATIONS! Your system is now universally GPU-ready.")
    else:
        print("⚠️  Some components are not detecting the GPU yet.")
    print("="*50)

if __name__ == "__main__":
    verify_gpu()
