.PHONY: sweep tune predict clean all

# Compare multiple models and select best
sweep:
	python src/sweep.py

# Tune GradientBoosting hyperparameters
tune:
	python src/tune_gbr.py

# Generate predictions
predict:
	python src/infer.py

# Clean model artifacts and cache
clean:
	rm -rf models/*.joblib models/*.csv models/.cache
	
# Run full pipeline (sweep, tune, predict)
all: sweep tune predict
