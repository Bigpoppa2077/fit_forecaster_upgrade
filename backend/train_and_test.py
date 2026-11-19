"""
Main Training and Testing Script for Fit Forecaster
Demonstrates the complete overhauled system
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.data_processor import DataProcessor
from src.models import SplitSpecificModels, XGBoostModel, EnsembleModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FitForecasterTrainer:
    """Main trainer class for the Fit Forecaster system"""
    
    def __init__(self, data_dir: str = "week_data"):
        self.data_dir = data_dir
        self.data_processor = DataProcessor()
        self.split_models = SplitSpecificModels()
        self.training_data = None
        self.test_data = None
        
    def load_and_process_data(self):
        """Load and process all historical data"""
        logger.info("Loading and processing historical data...")
        
        # Define file paths
        file_paths = {
            'monday': os.path.join(self.data_dir, 'mongym.csv'),
            'tuesday': os.path.join(self.data_dir, 'tuegym.csv'),
            'wednesday': os.path.join(self.data_dir, 'wedgym.csv'),
            'thursday': os.path.join(self.data_dir, 'thugym.csv'),
            'friday': os.path.join(self.data_dir, 'frigym.csv'),
            'saturday': os.path.join(self.data_dir, 'satgym.csv'),
            'sunday': os.path.join(self.data_dir, 'sungym.csv'),
        }
        
        # Real attendance reports from the app (if any) replace pretend counts
        reports_file = os.path.join('user_feedback', 'attendance_reports.csv')
        real_reports = pd.read_csv(reports_file) if os.path.exists(reports_file) else None
        
        # Process historical data
        self.training_data = self.data_processor.process_historical_data(file_paths, real_reports)
        
        # Validate data quality
        quality_report = self.data_processor.validate_data_quality(self.training_data)
        logger.info(f"Data quality report: {quality_report}")
        
        logger.info(f"Processed {len(self.training_data)} records")
        return self.training_data
    
    def train_models(self):
        """Train split-specific models"""
        logger.info("Training split-specific models...")
        
        # Train models for each split
        self.split_models.train_split_models(self.training_data)
        
        # Log training results
        for split_id, model_info in self.split_models.split_models.items():
            metrics = model_info['metrics']
            logger.info(f"Split {split_id} - MAE: {metrics['mae']:.3f}, R²: {metrics['r2']:.3f}")
    
    def evaluate_models(self, test_size: float = 0.2):
        """Evaluate model performance"""
        logger.info("Evaluating model performance...")
        
        # Split data for evaluation
        evaluation_results = {}
        
        for split_id, model_info in self.split_models.split_models.items():
            split_data = self.training_data[self.training_data['split_id'] == split_id].copy()
            
            if len(split_data) > 100:  # Need sufficient data for evaluation
                # Time-based split: study the earlier days, test on the last 20% of days
                # (the old random split tested on rows the model had already trained on)
                dates = sorted(split_data['date'].unique())
                cutoff = dates[int(len(dates) * (1 - test_size))]
                train_data = split_data[split_data['date'] < cutoff]
                test_data = split_data[split_data['date'] >= cutoff]

                # Prepare features
                feature_cols = model_info['feature_cols']
                X_train = train_data[feature_cols].fillna(0)
                y_train = train_data['visitor_count']
                X_test = test_data[feature_cols].fillna(0)
                y_test = test_data['visitor_count']

                # Train a fresh model on the earlier days only, then predict the hidden days
                eval_model = self.split_models.create_split_model(split_id)
                eval_model.train(X_train, y_train)
                y_pred = eval_model.predict(X_test)
                
                # Plot best fit line (actual vs predicted)
                import matplotlib.pyplot as plt
                import numpy as np
                plt.figure(figsize=(7, 6))
                plt.scatter(y_test, y_pred, alpha=0.5, label='Predicted vs Actual')
                min_val = min(y_test.min(), y_pred.min())
                max_val = max(y_test.max(), y_pred.max())
                plt.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect Fit (y=x)')
                # Regression line
                m, b = np.polyfit(y_test, y_pred, 1)
                plt.plot(y_test, m*y_test + b, 'g-', label='Regression Line')
                plt.xlabel('Actual Values')
                plt.ylabel('Predicted Values')
                plt.title(f'Actual vs Predicted for {split_id}')
                plt.legend()
                plt.tight_layout()
                plt.savefig(f'outputs/best_fit_{split_id}.png', dpi=300)
                plt.close()
                
                # Calculate metrics
                metrics = {
                    'mae': mean_absolute_error(y_test, y_pred),
                    'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
                    'r2': r2_score(y_test, y_pred),
                    'test_samples': len(y_test)
                }
                
                evaluation_results[split_id] = metrics
                logger.info(f"Split {split_id} evaluation - MAE: {metrics['mae']:.3f}, R²: {metrics['r2']:.3f}")
        
        self.evaluation_results = evaluation_results
        return evaluation_results
    
    def test_recommendation_engine(self):
        """Try the app's rule on the last simulated day: look 90 minutes (3 half hours) either side
        of a preferred time, pick the quietest, and keep the preferred time if moving saves less
        than half a person. Same rule as app.py, the API and the Flutter app."""
        logger.info("Testing the recommendation rule...")
        scenarios = [('Evening chest', 'Chest', 37), ('Morning cardio', 'Cardio', 14), ('Lunchtime legs', 'Legs', 25)]
        data = self.training_data
        last_day = data['date'].max()
        recommendations = []
        for label, split_id, pref in scenarios:
            if split_id not in self.split_models.split_models:
                continue
            info = self.split_models.split_models[split_id]
            day = data[(data['split_id'] == split_id) & (data['date'] == last_day)]
            preds = dict(zip(day['time_slot'].astype(int), np.clip(info['model'].predict(day[info['feature_cols']].fillna(0)), 0, None)))
            near = [s for s in range(pref - 3, pref + 4) if s in preds]
            best = min(near, key=lambda s: (round(preds[s], 1), abs(s - pref)))
            if preds[pref] - preds[best] < 0.5:
                best = pref
            recommendations.append({'scenario': label, 'preferred': pref, 'best': best,
                                    'people_preferred': preds[pref], 'people_best': preds[best]})
        return recommendations

    def create_visualizations(self, evaluation_results: dict):
        """Create performance visualizations"""
        logger.info("Creating performance visualizations...")
        
        # Create output directory
        os.makedirs('outputs', exist_ok=True)
        
        # 1. Model Performance Comparison
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # MAE comparison
        splits = list(evaluation_results.keys())
        maes = [evaluation_results[split]['mae'] for split in splits]
        
        axes[0, 0].bar(splits, maes, color='skyblue')
        axes[0, 0].set_title('Mean Absolute Error by Split')
        axes[0, 0].set_ylabel('MAE')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # R² comparison
        r2_scores = [evaluation_results[split]['r2'] for split in splits]
        
        axes[0, 1].bar(splits, r2_scores, color='lightgreen')
        axes[0, 1].set_title('R² Score by Split')
        axes[0, 1].set_ylabel('R²')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # RMSE comparison
        rmses = [evaluation_results[split]['rmse'] for split in splits]
        
        axes[1, 0].bar(splits, rmses, color='salmon')
        axes[1, 0].set_title('Root Mean Square Error by Split')
        axes[1, 0].set_ylabel('RMSE')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # Test samples comparison
        test_samples = [evaluation_results[split]['test_samples'] for split in splits]
        
        axes[1, 1].bar(splits, test_samples, color='gold')
        axes[1, 1].set_title('Test Samples by Split')
        axes[1, 1].set_ylabel('Number of Samples')
        axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig('outputs/model_performance.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Traffic Patterns
        if self.training_data is not None:
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # Average attendance by time slot
            time_attendance = self.training_data.groupby('time_slot')['visitor_count'].mean()
            
            axes[0, 0].plot(time_attendance.index, time_attendance.values, marker='o')
            axes[0, 0].set_title('Average Attendance by Time Slot')
            axes[0, 0].set_xlabel('Time Slot (30-min intervals)')
            axes[0, 0].set_ylabel('Average Visitors')
            axes[0, 0].grid(True)
            
            # Attendance by day of week
            day_attendance = self.training_data.groupby('day_of_week')['visitor_count'].mean()
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            
            axes[0, 1].bar(range(len(day_attendance)), day_attendance.values, color='lightblue')
            axes[0, 1].set_title('Average Attendance by Day of Week')
            axes[0, 1].set_xlabel('Day of Week')
            axes[0, 1].set_ylabel('Average Visitors')
            axes[0, 1].set_xticks(range(len(day_attendance)))
            axes[0, 1].set_xticklabels(day_names)
            
            # Attendance by split
            split_attendance = self.training_data.groupby('split_id')['visitor_count'].mean()
            
            axes[1, 0].bar(split_attendance.index, split_attendance.values, color='lightgreen')
            axes[1, 0].set_title('Average Attendance by Split')
            axes[1, 0].set_xlabel('Split')
            axes[1, 0].set_ylabel('Average Visitors')
            axes[1, 0].tick_params(axis='x', rotation=45)
            
            # Heatmap: Time vs Day
            pivot_data = self.training_data.pivot_table(
                values='visitor_count', 
                index='time_slot', 
                columns='day_of_week', 
                aggfunc='mean'
            ).fillna(0)
            
            sns.heatmap(pivot_data, ax=axes[1, 1], cmap='YlOrRd', cbar_kws={'label': 'Average Visitors'})
            axes[1, 1].set_title('Attendance Heatmap: Time vs Day')
            axes[1, 1].set_xlabel('Day of Week')
            axes[1, 1].set_ylabel('Time Slot')
            
            plt.tight_layout()
            plt.savefig('outputs/traffic_patterns.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        logger.info("Visualizations saved to outputs/ directory")
    
    def save_models(self, output_dir: str = "models"):
        """Save trained models"""
        logger.info(f"Saving models to {output_dir}...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        for split_id, model_info in self.split_models.split_models.items():
            split_dir = os.path.join(output_dir, split_id.lower())
            model_info['model'].save_ensemble(split_dir)
            
            # Save metrics
            metrics_file = os.path.join(split_dir, 'metrics.json')
            import json
            with open(metrics_file, 'w') as f:
                json.dump(model_info['metrics'], f, indent=2)
        
        # Save the honest (hidden-days) scores so the app can show them
        if getattr(self, 'evaluation_results', None):
            from src.realtime_learning import write_evaluation
            write_evaluation({k: {'r2': float(v['r2']), 'mae': float(v['mae']),
                                  'test_samples': int(v['test_samples'])}
                              for k, v in self.evaluation_results.items()}, output_dir)
        logger.info("Models saved successfully")
    
    def run_complete_pipeline(self):
        """Run the complete training and testing pipeline"""
        logger.info("Starting Fit Forecaster training pipeline...")
        
        try:
            # 1. Load and process data
            self.load_and_process_data()
            
            # 2. Train models
            self.train_models()
            
            # 3. Evaluate models
            evaluation_results = self.evaluate_models()
            
            # 4. Test recommendation engine
            recommendations = self.test_recommendation_engine()
            
            # 5. Create visualizations
            self.create_visualizations(evaluation_results)
            
            # 6. Save models
            self.save_models()
            
            # 7. Print summary
            self.print_summary(evaluation_results, recommendations)
            
            logger.info("Pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
    
    def print_summary(self, evaluation_results: dict, recommendations: list):
        """Print a summary of results"""
        print("\n" + "="*60)
        print("FIT FORECASTER TRAINING SUMMARY")
        print("="*60)
        
        print(f"\n📊 MODEL PERFORMANCE:")
        print("-" * 40)
        for split_id, metrics in evaluation_results.items():
            print(f"{split_id:>10}: MAE={metrics['mae']:6.3f}, R²={metrics['r2']:6.3f}, Test Samples={metrics['test_samples']:3d}")
        
        print(f"\n🎯 RECOMMENDATION RULE (last simulated day):")
        print("-" * 40)
        t = lambda slot: f"{slot // 2:02d}:{(slot % 2) * 30:02d}"
        for r in recommendations:
            print(f"{r['scenario']:>16}: wanted {t(r['preferred'])} (~{r['people_preferred']:.1f} people) -> "
                  f"go at {t(r['best'])} (~{r['people_best']:.1f} people)")
        
        print(f"\n📁 OUTPUTS:")
        print("-" * 40)
        print("• Models saved to: models/")
        print("• Visualizations saved to: outputs/")
        print(f"• Training data processed: {len(self.training_data)} records")
        print(f"• Splits trained: {len(self.split_models.split_models)}")
        
        print("\n" + "="*60)

def main():
    """Main function to run the training pipeline"""
    # Fix the random seed so every run simulates the same visits and gives the same scores
    np.random.seed(42)

    # Create trainer instance
    trainer = FitForecasterTrainer()
    
    # Run complete pipeline
    trainer.run_complete_pipeline()

if __name__ == "__main__":
    main() 