#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

// Функция для безопасного извлечения строк из структур Vulkan
void decode_str(const char* src, char* dst, size_t dst_size) {
    if (!src || !dst || dst_size == 0) {
        if (dst && dst_size > 0) dst[0] = '\0';
        return;
    }

    // Найти нулевой символ или первый символ null terminator
    size_t len = 0;
    while (len < dst_size - 1 && src[len] != '\0') {
        len++;
    }

    // Копируем строку до нулевого символа или до заполнения буфера
    memcpy(dst, src, len);
    dst[len] = '\0';
}

// Функция для определения типа устройства
const char* device_type_name(VkPhysicalDeviceType device_type) {
    switch (device_type) {
        case VK_PHYSICAL_DEVICE_TYPE_OTHER:
            return "OTHER";
        case VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU:
            return "INTEGRATED_GPU";
        case VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU:
            return "DISCRETE_GPU";
        case VK_PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU:
            return "VIRTUAL_GPU";
        case VK_PHYSICAL_DEVICE_TYPE_CPU:
            return "CPU";
        default:
            return "UNKNOWN";
    }
}

// Проверка поддержки расширения для получения свойств драйвера
VkBool32 device_supports_driver_props(VkPhysicalDevice device) {
    uint32_t extension_count;
    VkResult result = vkEnumerateDeviceExtensionProperties(device, NULL, &extension_count, NULL);
    if (result != VK_SUCCESS) {
        return VK_FALSE;
    }

    if (extension_count == 0) {
        return VK_FALSE;
    }

    VkExtensionProperties* extensions = malloc(sizeof(VkExtensionProperties) * extension_count);
    result = vkEnumerateDeviceExtensionProperties(device, NULL, &extension_count, extensions);
    if (result != VK_SUCCESS) {
        free(extensions);
        return VK_FALSE;
    }

    VkBool32 supports = VK_FALSE;
    for (uint32_t i = 0; i < extension_count; i++) {
        if (strcmp(extensions[i].extensionName, VK_KHR_DRIVER_PROPERTIES_EXTENSION_NAME) == 0) {
            supports = VK_TRUE;
            break;
        }
    }

    free(extensions);
    return supports;
}

int main() {
    // Инициализация Vulkan
    VkApplicationInfo app_info = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pNext = NULL,
        .pApplicationName = "GPUInfo",
        .applicationVersion = VK_MAKE_VERSION(1, 0, 0),
        .pEngineName = "NoEngine",
        .engineVersion = VK_MAKE_VERSION(1, 0, 0),
        .apiVersion = VK_API_VERSION_1_0
    };

    // Проверим, какие расширения доступны
    uint32_t instance_extension_count;
    VkResult result = vkEnumerateInstanceExtensionProperties(NULL, &instance_extension_count, NULL);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "Failed to get instance extension count\n");
        return -1;
    }

    VkExtensionProperties* instance_extensions = NULL;
    if (instance_extension_count > 0) {
        instance_extensions = malloc(sizeof(VkExtensionProperties) * instance_extension_count);
        result = vkEnumerateInstanceExtensionProperties(NULL, &instance_extension_count, instance_extensions);
        if (result != VK_SUCCESS) {
            fprintf(stderr, "Failed to enumerate instance extensions\n");
            free(instance_extensions);
            return -1;
        }
    }

    // Проверим, поддерживается ли нужное расширение
    const char* required_instance_extensions[] = {
        VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME
    };
    uint32_t enabled_extension_count = 0;
    const char** enabled_extensions = NULL;

    if (instance_extensions) {
        for (uint32_t i = 0; i < instance_extension_count; i++) {
            if (strcmp(instance_extensions[i].extensionName, VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME) == 0) {
                enabled_extensions = required_instance_extensions;
                enabled_extension_count = 1;
                break;
            }
        }
        free(instance_extensions);
    }

    VkInstanceCreateInfo create_info = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = NULL,
        .flags = 0,
        .pApplicationInfo = &app_info,
        .enabledLayerCount = 0,
        .ppEnabledLayerNames = NULL,
        .enabledExtensionCount = enabled_extension_count,
        .ppEnabledExtensionNames = enabled_extensions
    };

    VkInstance instance;
    result = vkCreateInstance(&create_info, NULL, &instance);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "Failed to create Vulkan instance\n");
        return -1;
    }

    // Получаем список физических устройств
    uint32_t device_count;
    result = vkEnumeratePhysicalDevices(instance, &device_count, NULL);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "Failed to get physical device count\n");
        vkDestroyInstance(instance, NULL);
        return -1;
    }

    if (device_count == 0) {
        printf("No Vulkan-compatible GPUs found\n");
        vkDestroyInstance(instance, NULL);
        return 0;
    }

    VkPhysicalDevice* devices = malloc(sizeof(VkPhysicalDevice) * device_count);
    result = vkEnumeratePhysicalDevices(instance, &device_count, devices);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "Failed to enumerate physical devices\n");
        vkDestroyInstance(instance, NULL);
        free(devices);
        return -1;
    }

    // Обрабатываем каждое устройство
    for (uint32_t i = 0; i < device_count; i++) {
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(devices[i], &props);

        uint32_t gpu_id = props.deviceID;
        char device_name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];
        decode_str(props.deviceName, device_name, sizeof(device_name));

        uint32_t api_version = props.apiVersion;
        uint32_t driver_version = props.driverVersion;
        const char* device_type = device_type_name(props.deviceType);

        char driver_name[VK_MAX_EXTENSION_NAME_SIZE] = "Unknown";
        char driver_info[VK_MAX_EXTENSION_NAME_SIZE] = "Unknown";

        if (device_supports_driver_props(devices[i])) {
            // Используем VkPhysicalDeviceProperties2 для получения дополнительной информации
            VkPhysicalDeviceDriverProperties driver_props = {
                .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES,
                .pNext = NULL
            };

            VkPhysicalDeviceProperties2 props2 = {
                .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,
                .pNext = &driver_props
            };

            // Получаем расширенные свойства
            PFN_vkGetPhysicalDeviceProperties2 vkGetPhysicalDeviceProperties2 =
                (PFN_vkGetPhysicalDeviceProperties2)vkGetInstanceProcAddr(instance, "vkGetPhysicalDeviceProperties2");

            if (vkGetPhysicalDeviceProperties2 != NULL) {
                vkGetPhysicalDeviceProperties2(devices[i], &props2);
                decode_str(driver_props.driverName, driver_name, sizeof(driver_name));
                decode_str(driver_props.driverInfo, driver_info, sizeof(driver_info));
            }
        }

        printf("GPU #%u\n", i);
        printf("gpu_id: %u\n", gpu_id);
        printf("device_name: %s\n", device_name);
        printf("driver_name: %s\n", driver_name);
        printf("driver_info: %s\n", driver_info);
        printf("api_version: %u.%u.%u\n",
               VK_VERSION_MAJOR(api_version),
               VK_VERSION_MINOR(api_version),
               VK_VERSION_PATCH(api_version));
        printf("driver_version: %u.%u.%u\n",
               VK_VERSION_MAJOR(driver_version),
               VK_VERSION_MINOR(driver_version),
               VK_VERSION_PATCH(driver_version));
        printf("device_type: %s\n", device_type);
        printf("\n");
    }

    // Освобождаем ресурсы
    free(devices);
    vkDestroyInstance(instance, NULL);

    return 0;
}
