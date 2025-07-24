#!/bin/bash
# Скрипт для запуска Ansible playbook создания пользователя

# Убедитесь, что у вас есть SSH ключ
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "SSH ключ не найден. Создаем новый..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

echo "Запуск Ansible playbook для создания пользователя chernyavskyda..."

# Запуск playbook
ansible-playbook -i hosts.ini sshkeys.yaml

echo "Playbook выполнен. Проверьте результаты выше."

# Дополнительная проверка подключения
echo "Проверка SSH подключения к первому серверу..."
ansible all -i hosts.ini -m ping -u chernyavskyda --limit 192.168.30.58
