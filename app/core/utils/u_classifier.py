import fnmatch
import logging
import os
import pickle

import numpy as np
import pandas as pd
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ClassifierService:
    threshold_value = 500
    accuracy_score = ''

    def __init__(self):
        self.models_folder = os.path.join(settings.DATA_DIR, 'models')
        if not os.path.exists(self.models_folder):
            os.makedirs(self.models_folder)
        self.classifier = None

    def _get_last_model(self, model_file=None):
        # ! deprecated
        if not model_file:
            model_files = fnmatch.filter(os.listdir(self.models_folder), 'match_model_*.pkl')
            last_date = None
            last_model_file = None
            for model_file in model_files:
                date_str = model_file.lstrip('match_model_').rstrip('.pkl')
                model_date = timezone.utc.localize(timezone.datetime.strptime(date_str, '%Y.%m.%d_%H%M'))
                if not last_date or model_date > last_date:
                    last_date = model_date
                    last_model_file = os.path.join(self.models_folder, model_file)
            model_file = last_model_file
        if model_file:
            with open(model_file, 'rb') as file:
                classifier = pickle.load(file)
                return classifier
        return None

    def ready(self):
        return self.classifier is not None

    def load_model(self, pkl_filename):
        if pkl_filename:
            file_path = os.path.join(self.models_folder, pkl_filename)
            with open(file_path, 'rb') as file:
                classifier = pickle.load(file)
                self.classifier = classifier
        else:
            self.classifier = None

    def _train_new_model(self, values):
        df = pd.DataFrame(values)
        df.dropna(subset=['verified_similarity'], inplace=True)
        df_size = df.shape[0]
        if df_size < self.threshold_value:
            logging.warning(
                f'_train_new_model: not enough records for training (now {df_size}, you need {self.threshold_value})',
            )
            return None, {
                'accuracy_score': np.nan,
                'confusion_matrix': '',
            }
        df['verified_similarity'] = df['verified_similarity'].apply(lambda x: 1 if x else 0)
        X = df.iloc[:, 1:11].values
        y = df.iloc[:, 12].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)
        sc = StandardScaler()
        X_train = sc.fit_transform(X_train)
        X_test = sc.transform(X_test)

        classifier = RandomForestClassifier(n_estimators=20, random_state=0)
        classifier.fit(X_train, y_train)
        y_pred = classifier.predict(X_test)

        return classifier, {
            'accuracy_score': accuracy_score(y_test, y_pred),
            'confusion_matrix': str(confusion_matrix(y_test, y_pred)),
        }

    def create_new_model(self, values):
        try:
            classifier, estimate = self._train_new_model(values)
            if not classifier:
                return None, None
            date_str = timezone.now().strftime('%Y.%m.%d_%H%M')
            pkl_filename = f'match_model_{date_str}.pkl'
            pkl_path = os.path.join(self.models_folder, pkl_filename)

            with open(pkl_path, 'wb') as file:
                pickle.dump(classifier, file)
        except Exception as e:
            logging.error(
                f'create_new_model error: {type(e)}',
                exc_info=True,
            )
            return None, None
        return pkl_filename, estimate

    def predict(self, s_result, model_file=None):
        if not s_result:
            logging.error(
                f'predict error: invalid param',
                extra={
                    's_result': s_result,
                },
            )
        if self.classifier is None:
            if model_file is None:
                logging.error(
                    f'predict error: classifier is not initialized',
                    extra={
                        's_result': s_result,
                        'model_file': model_file,
                    },
                )
                return None
            self.load_model(model_file)
        # q_result = SearchResult.objects.filter(id=s_result_id).values(
        #     'id', 'mention_similar', 'partial_matching',
        #     'similar_data__BlockMeanHash',
        #     'similar_data__RadialVarianceHash',
        #     'similar_data__AverageHash',
        #     'similar_data__MarrHildrethHash',
        #     'similar_data__PHash', 'similar_data__delta_color',
        #     'similar_data__base_dominant_color_r',
        #     'similar_data__base_dominant_color_g',
        #     'similar_data__base_dominant_color_b',
        #     'verified_similarity',
        # )
        # q_result.count()
        # if q_result.count() != 1:
        #     return -1
        # s_result = q_result.first()
        df_pred = pd.DataFrame([s_result])
        x_pred = df_pred.iloc[:, 1:11].values
        y_pred = self.classifier.predict(x_pred)
        return y_pred[0] == 1
