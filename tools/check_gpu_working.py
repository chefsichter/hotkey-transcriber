import torch

print(torch.version)
print(torch.version.hip)   # hip-Version sollte nicht None sein bei ROCm
print(torch.cuda.is_available())  # Sollte True sein, auch bei AMD!
print(torch.cuda.device_count())  # Anzahl der GPUs
print(torch.cuda.get_device_name(0))  # Name der ersten GPU