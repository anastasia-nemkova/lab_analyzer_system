# Lab Analyzer: Система приема и анализа лабораторных работ

## Описание

Ядро системы онлайн-школы для безопасного приема, валидации и анализа лабораторных работ.

## Установка и запуск

Проект использует `src-layout` и `pyproject.toml`.

1. Клонируйте репозиторий и создайте виртуальное окружение:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate   # Windows
   ```
2. Установите пакет в режиме разработки:
   ```bash
   pip install -e ".[dev]"
   ```
