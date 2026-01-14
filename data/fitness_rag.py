import chromadb
import json
import os
from sentence_transformers import SentenceTransformer


class FitnessRAGSystem:
    def __init__(self, persist_dir: str = "./fitness_chroma_db"):
        # Инициализация ChromaDB (новый API)
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Загружаем модель для эмбеддингов
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Хранилище документов в памяти
        self.documents = []
        self.collections_data = {}
        
        # Кэш полных данных планов
        self._plans_data_cache = {}
        
        # Создаем коллекции
        self.create_collections()
        
        # Загружаем данные
        self.load_data()

    def create_collections(self):
        """Создаем коллекции в ChromaDB"""
        self.collections = {
            "exercises": self.client.get_or_create_collection(
                name="exercises",
                metadata={"description": "Упражнения с ASCII-схемами"}
            ),
            "workout_plans": self.client.get_or_create_collection(
                name="workout_plans",
                metadata={"description": "Тренировочные планы на 4 недели"}
            ),
            "warmup": self.client.get_or_create_collection(
                name="warmup",
                metadata={"description": "Разминка 5 минут"}
            )
        }
        print("✓ Коллекции ChromaDB созданы")

    def load_data(self, data_dir: str = "data/fitness_rag_data"):
        """Загружаем данные из JSON файлов"""
        
        if not os.path.exists(data_dir):
            print(f"⚠️ Директория {data_dir} не найдена")
            return
        
        self.documents = []
        
        # 1. Загружаем РАЗМИНКУ
        warmup_path = os.path.join(data_dir, "warmup_routine.json")
        if os.path.exists(warmup_path):
            print("Загрузка разминки...")
            with open(warmup_path, "r", encoding="utf-8") as f:
                warmup = json.load(f)
            
            warmup_text = f"""
            Разминка: {warmup['name']}
            Описание: {warmup['description']}
            Длительность: {warmup['total_duration']} секунд
            Упражнения: {', '.join([ex['name'] for ex in warmup['exercises']])}
            """
            
            self.collections["warmup"].add(
                documents=[warmup_text],
                metadatas=[{"type": "warmup", "duration": warmup['total_duration']}],
                ids=["warmup_001"]
            )
            
            # Сохраняем полные данные
            self.documents.append({"type": "warmup", "data": warmup})
            print("✓ Разминка загружена в ChromaDB")

        # 2. Загружаем УПРАЖНЕНИЯ
        exercises_path = os.path.join(data_dir, "exercises_library.json")
        if os.path.exists(exercises_path):
            print("Загрузка упражнений...")
            with open(exercises_path, "r", encoding="utf-8") as f:
                exercises_data = json.load(f)
            
            exercise_texts = []
            exercise_metadatas = []
            exercise_ids = []
            
            for exercise in exercises_data["exercises"]:
                text = f"""
                Упражнение: {exercise['name']}
                Описание: {exercise['description']}
                Основные мышцы: {', '.join(exercise['primary_muscles'])}
                Оборудование: {', '.join(exercise['equipment'])}
                Сложность: {exercise['difficulty']}/5
                """
                exercise_texts.append(text)
                exercise_metadatas.append({
                    "id": exercise["id"],
                    "name": exercise["name"],
                    "muscles": json.dumps(exercise["primary_muscles"]),
                    "equipment": json.dumps(exercise["equipment"]),
                    "difficulty": exercise["difficulty"],
                    "ascii": json.dumps(exercise.get("ascii_schematic", []))
                })
                exercise_ids.append(exercise["id"])
            
            # Генерируем эмбеддинги и добавляем
            exercise_embeddings = self.model.encode(exercise_texts).tolist()
            self.collections["exercises"].add(
                embeddings=exercise_embeddings,
                documents=exercise_texts,
                metadatas=exercise_metadatas,
                ids=exercise_ids
            )
            
            self.documents.append({"type": "exercises", "count": len(exercise_ids)})
            print(f"✓ Загружено {len(exercise_ids)} упражнений в ChromaDB")

        # 3. Загружаем ПЛАНЫ ТРЕНИРОВОК
        plans_path = os.path.join(data_dir, "workout_plans_full.json")
        if os.path.exists(plans_path):
            print("Загрузка тренировочных планов...")
            with open(plans_path, "r", encoding="utf-8") as f:
                plans_data = json.load(f)
            
            plan_texts = []
            plan_metadatas = []
            plan_ids = []
            
            # Кэшируем полные данные планов
            self._plans_data_cache = {}
            
            for plan_key, plan in plans_data["plans"].items():
                # Сохраняем полные данные плана
                self._plans_data_cache[plan_key] = plan
                
                exercises_names = [ex["name"] for ex in plan["exercises"]]
                text = f"""
                План: {plan['name']}
                Для: {plan['category']['gender']}, возраст {plan['category']['age_group']}
                Неделя: {plan['week']}, День: {plan['day']}
                Мышцы: {', '.join(plan['target_muscles'])}
                Интенсивность: {plan['intensity_level']}
                Упражнения: {', '.join(exercises_names)}
                """
                plan_texts.append(text)
                plan_metadatas.append({
                    "key": plan_key,
                    "gender": plan['category']['gender'],
                    "age_group": plan['category']['age_group'],
                    "week": plan["week"],
                    "day": plan["day"],
                    "muscles": json.dumps(plan["target_muscles"]),
                    "intensity_level": plan["intensity_level"]
                })
                plan_ids.append(plan_key)
            
            # Генерируем эмбеддинги и добавляем планы
            plan_embeddings = self.model.encode(plan_texts).tolist()
            self.collections["workout_plans"].add(
                embeddings=plan_embeddings,
                documents=plan_texts,
                metadatas=plan_metadatas,
                ids=plan_ids
            )
            
            self.documents.append({"type": "workout_plans", "count": len(plan_ids)})
            print(f"✓ Загружено {len(plan_ids)} тренировочных планов в ChromaDB")

    def get_warmup(self):
        """Получить разминку"""
        results = self.collections["warmup"].get(ids=["warmup_001"])
        return results

    def search_exercises(self, query, n_results=5):
        """Поиск упражнений по запросу"""
        query_embedding = self.model.encode([query]).tolist()
        results = self.collections["exercises"].query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results

    def get_workout_plan(self, gender, age_group, week, day):
        """
        Получить конкретный план тренировки с полными данными упражнений.
        """
        # Формируем ключ как в load_data
        plan_key = f"{gender}_{age_group.replace('-', '_')}_week{week}_day{day}"
        
        # Сначала пробуем из кэша
        if plan_key in self._plans_data_cache:
            return self._plans_data_cache[plan_key]
        
        # Если нет в кэше, ищем в ChromaDB
        results = self.collections["workout_plans"].get(ids=[plan_key])
        
        if results and results.get('metadatas') and len(results['metadatas']) > 0:
            # Возвращаем структуру как из кэша
            meta = results['metadatas'][0]
            return {
                "name": f"Тренировка {week}.{day}",
                "week": week,
                "day": day,
                "target_muscles": json.loads(meta.get("muscles", "[]")),
                "intensity_level": meta.get("intensity_level", "medium"),
                "exercises": [],
                "warmup": [],
                "cooldown": []
            }
        
        return None

    def search_similar_plans(self, query, n_results=3):
        """Поиск похожих планов по запросу"""
        query_embedding = self.model.encode([query]).tolist()
        results = self.collections["workout_plans"].query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results
        
    def get_plans_by_category(self, gender, age_group):
        """Получить все планы для категории"""
        all_plans = self.collections["workout_plans"].get()
        
        # Фильтруем по категории
        filtered = {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "embeddings": []
        }
        
        for i, meta in enumerate(all_plans["metadatas"]):
            if meta["gender"] == gender and meta["age_group"] == age_group:
                filtered["documents"].append(all_plans["documents"][i])
                filtered["metadatas"].append(meta)
                filtered["ids"].append(all_plans["ids"][i])
                if "embeddings" in all_plans:
                    filtered["embeddings"].append(all_plans["embeddings"][i])
        
        return filtered

    def add_document(self, text: str, metadata: dict = None):
        """
        Добавляет новый документ в коллекцию упражнений.

        Args:
            text: Текст документа
            metadata: Метаданные документа
        """
        embedding = self.model.encode([text]).tolist()[0]
        
        doc_id = f"doc_{len(self.documents)}_{hash(text)[:8]}"
        
        self.collections["exercises"].add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )
        
        self.documents.append({
            "type": "custom",
            "id": doc_id,
            "metadata": metadata
        })
        
        return doc_id

    def get_status(self) -> dict:
        """Возвращает статус системы RAG."""
        status = {
            "documents_count": len(self.documents),
            "persist_dir": self.persist_dir,
            "collections": {}
        }
        
        for name, collection in self.collections.items():
            try:
                status["collections"][name] = {
                    "count": collection.count(),
                    "ready": True
                }
            except Exception as e:
                status["collections"][name] = {
                    "count": 0,
                    "ready": False,
                    "error": str(e)
                }
        
        return status


# ИСПОЛЬЗОВАНИЕ
if __name__ == "__main__":
    print("Инициализация RAG системы с ChromaDB...")
    rag = FitnessRAGSystem()
    
    print("\n" + "="*50)
    print("✅ RAG СИСТЕМА ГОТОВА К РАБОТЕ!")
    print("="*50)
    
    # 1. Получаем разминку
    print("\n1️⃣ Разминка:")
    warmup = rag.get_warmup()
    print(f"   {warmup['documents'][0][:150]}...")
    
    # 2. Ищем упражнения
    print("\n2️⃣ Поиск упражнений для груди:")
    exercises = rag.search_exercises("упражнения для грудных мышц без оборудования", n_results=3)
    for i, ex in enumerate(exercises['metadatas'][0]):
        print(f"   {i+1}. {ex['name']} (сложность: {ex['difficulty']})")
    
    # 3. Получаем план
    print("\n3️⃣ План тренировки:")
    plan = rag.get_workout_plan("male", "18-30", 1, 1)
    if plan['metadatas']:
        meta = plan['metadatas'][0]
        print(f"   Пол: {meta['gender']}, Возраст: {meta['age_group']}")
        print(f"   Неделя {meta['week']}, День {meta['day']}")
    
    # 4. Поиск похожих планов
    print("\n4️⃣ Поиск планов для новичков:")
    similar = rag.search_similar_plans("легкая тренировка для начинающих", n_results=2)
    for i, meta in enumerate(similar['metadatas'][0]):
        print(f"   {i+1}. Интенсивность: {meta['intensity_level']}")