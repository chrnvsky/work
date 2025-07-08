import requests
import docker
import inquirer
import re
import sys
from typing import List, Dict

# Настройки
# GITLAB_TOKEN = ""
# GITLAB_PROJECT_ID = ""
# GITLAB_API_URL = ""
# GITLAB_REGISTRY = ""
# GITLAB_NAMESPACE = ""
# DOCKERHUB_NAMESPACE = ""

# Инициализация клиента Docker
docker_client = docker.from_env()

def login_to_gitlab_registry() -> None:
    """Авторизация в реестре GitLab."""
    try:
        docker_client.login(
            username="gitlab-ci-token",
            password=GITLAB_TOKEN,
            registry=GITLAB_REGISTRY
        )
        print("[INFO] Успешная авторизация в GitLab Registry")
    except docker.errors.APIError as e:
        print(f"[ERROR] Не удалось авторизоваться в GitLab Registry: {e}")
        sys.exit(1)

def extract_version(tag: str) -> tuple:
    """Извлечение числовой версии из тега для сортировки."""
    match = re.match(r"^(\d+)(\.(\d+))?(\.(\d+))?(-[a-zA-Z0-9]+)?$", tag)
    if not match:
        return (0, 0, 0, tag)  # Для нечисловых тегов
    major = int(match.group(1))
    minor = int(match.group(3) or 0)
    patch = int(match.group(5) or 0)
    suffix = match.group(6) or ""
    return (major, minor, patch, suffix)

def get_dockerhub_tags(image: str) -> List[str]:
    """Получение тегов с Docker Hub."""
    tags = []
    url = f"https://hub.docker.com/v2/repositories/{DOCKERHUB_NAMESPACE}/{image}/tags/?page_size=100"
    try:
        while url:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            tags.extend(
                tag["name"] for tag in data["results"]
                if re.match(r"^[0-9]+(\.[0-9]+(\.[0-9]+)?)?(-[a-zA-Z0-9]+)?$", tag["name"])
            )
            url = data.get("next")
#       print(f"[DEBUG] Docker Hub tags for {image}: {tags}")
        return sorted(tags, key=extract_version, reverse=True)  # Сортировка от новых к старым
    except requests.RequestException as e:
        print(f"[ERROR] Не удалось получить теги с Docker Hub для {image}: {e}")
        return []

def get_gitlab_tags(repo_id: str) -> List[str]:
    """Получение тегов из GitLab Registry."""
    try:
        response = requests.get(
            f"{GITLAB_API_URL}/projects/{GITLAB_PROJECT_ID}/registry/repositories/{repo_id}/tags",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        tags = [tag["name"] for tag in response.json()]
#       print(f"[DEBUG] GitLab tags for repo_id {repo_id}: {tags}")
        return sorted(tags, key=extract_version, reverse=True)
    except requests.RequestException as e:
        print(f"[ERROR] Не удалось получить теги из GitLab для repo_id {repo_id}: {e}")
        return []

def get_gitlab_repositories() -> List[Dict[str, str]]:
    """Получение списка репозиториев из GitLab."""
    try:
        response = requests.get(
            f"{GITLAB_API_URL}/projects/{GITLAB_PROJECT_ID}/registry/repositories",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        return [
            {"id": repo["id"], "path": repo["path"], "name": repo["path"].split("/")[-1]}
            for repo in response.json()
        ]
    except requests.RequestException as e:
        print(f"[ERROR] Не удалось получить список репозиториев: {e}")
        return []

def sync_image(image_name: str, tag: str) -> bool:
    """Синхронизация одного тега образа."""
    print(f"[INFO] Загружаем {image_name}:{tag}...")
    try:
        docker_client.images.pull(f"{DOCKERHUB_NAMESPACE}/{image_name}", tag=tag)
        target_image = f"{GITLAB_REGISTRY}/{GITLAB_NAMESPACE}/{image_name}:{tag}"
        image = docker_client.images.get(f"{DOCKERHUB_NAMESPACE}/{image_name}:{tag}")
        image.tag(target_image)
        docker_client.images.push(target_image)
        print(f"✅ Успешно загружено: {image_name}:{tag}")
        return True
    except docker.errors.APIError as e:
        print(f"❌ Ошибка при синхронизации {image_name}:{tag}: {e}")
        return False

def main():
    login_to_gitlab_registry()
    while True:
        repositories = get_gitlab_repositories()
        if not repositories:
            print("[ERROR] Не удалось загрузить репозитории. Завершение работы.")
            sys.exit(1)
        repo_choices = [(repo["name"], repo) for repo in repositories]
        repo_choices.append(("Все образы", "all"))
        repo_choices.append(("Выход", "exit"))
        question = [inquirer.List("repo", message="Выберите образ для синхронизации", choices=repo_choices)]
        answers = inquirer.prompt(question)
        if not answers or answers["repo"] == "exit":
            print("Выход")
            sys.exit(0)
        selected_repos = repositories if answers["repo"] == "all" else [answers["repo"]]
        for repo in selected_repos:
            print("=" * 30)
            print(f"[INFO] Обрабатывается: {repo['path']}")
            image_name = repo["name"]
            print(f"[INFO] Имя образа: {image_name}")
            print("[INFO] Получаем теги с Docker Hub...")
            dockerhub_tags = get_dockerhub_tags(image_name)
            gitlab_tags = get_gitlab_tags(repo["id"])
            # Находим отсутствующие теги
            missing_tags = sorted(
                list(set(dockerhub_tags) - set(gitlab_tags)),
                key=extract_version,
                reverse=True
            )[:20]  # Ограничиваем до 20 самых новых
#           print(f"[DEBUG] Missing tags: {missing_tags}")
            if not missing_tags:
                print("[INFO] Все теги уже синхронизированы")
                continue
            tag_choices = [(tag, tag) for tag in missing_tags]
            tag_choices.append(("Все теги", "all"))
            tag_choices.append(("Пропустить", "skip"))
            print("Доступные теги для синхронизации:")
            question = [inquirer.List("tag", message="Выберите тег для синхронизации", choices=tag_choices)]
            tag_answer = inquirer.prompt(question)
            if not tag_answer or tag_answer["tag"] == "skip":
                print("[INFO] Пропускаем образ...")
                continue
            tags_to_sync = missing_tags if tag_answer["tag"] == "all" else [tag_answer["tag"]]
            for tag in tags_to_sync:
                sync_image(image_name, tag)
        print("✅ Синхронизация завершена для выбранных образов")

if __name__ == "__main__":
    main()