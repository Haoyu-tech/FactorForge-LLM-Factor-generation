from __future__ import annotations
from typing import Callable
import numpy as np

TARGET_DAILY_SIGMA = 0.04 / np.sqrt(252.0)
_DOUBLE_EPS = np.finfo(np.float64).eps
_SQRT_DOUBLE_EPS = np.sqrt(_DOUBLE_EPS)


def _as_finite_float64(value: object, *, ndim: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != ndim or not np.isfinite(array).all():
        raise ValueError(f"Invalid {name}")
    return array


def spatial_factors(Y: object, rmax: int) -> np.ndarray:
    matrix = _as_finite_float64(Y, ndim=2, name="spatial-factor input")
    nr, nc = matrix.shape
    rmax = int(rmax)
    if nr < 3 or nc < 2 or rmax < 1 or (rmax + 1 > min(nr - 1, nc)):
        raise ValueError("Invalid rmax")
    # Reproduce the spatial-factor step used by the baseline POET path.
    shifted = matrix - matrix[0]
    squared_norm = np.einsum("ij,ij->i", shifted, shifted)
    distance2 = squared_norm[:, None] + squared_norm[None, :] - 2.0 * (shifted @ shifted.T)
    np.fill_diagonal(distance2, np.inf)
    bad_i, bad_j = np.where(np.triu(distance2 <= 0.0, k=1))
    for i, j in zip(bad_i.tolist(), bad_j.tolist()):
        exact = float(np.sum((matrix[i] - matrix[j]) ** 2))
        if exact <= 0.0:
            raise ValueError("Duplicate spatial-factor rows")
        distance2[i, j] = distance2[j, i] = exact
    with np.errstate(divide="ignore", invalid="ignore"):
        adjacency = 1.0 / distance2
    np.fill_diagonal(adjacency, 0.0)
    laplacian = np.diag(np.sum(adjacency, axis=1)) - adjacency
    eigenvalues, eigenvectors = np.linalg.eigh((laplacian + laplacian.T) / 2.0)
    order = np.arange(eigenvalues.size - 1, -1, -1)
    eigenvalues, eigenvectors = (eigenvalues[order], eigenvectors[:, order])
    keep = eigenvalues > eigenvalues[0] * 1e-13
    weighted = (
        np.sqrt(np.maximum(eigenvalues[keep], 0.0))[:, None] * eigenvectors[:, keep].T @ shifted
    )
    weighted *= np.sqrt(2.0 / (nr * (nr - 1.0)))
    _, singular_values, right_t = np.linalg.svd(weighted, full_matrices=False)
    values = singular_values[: rmax + 1] ** 2
    rank = int(np.argmax(values[:rmax] / values[1 : rmax + 1])) + 1
    return right_t[:rank].T.copy()


def gamma_path(gamma_design: object, mu: object) -> np.ndarray:
    design = _as_finite_float64(gamma_design, ndim=2, name="gamma design")
    mean = _as_finite_float64(mu, ndim=1, name="synthetic mean")
    nr, nc = design.shape
    if mean.size != nc:
        raise ValueError("Invalid synthetic mean")
    # Remove the estimated common-factor space before measuring idiosyncratic scale.
    vectors = spatial_factors(design, min(8, nc - 1, nr - 2))
    centered = design - mean
    projected = centered - centered @ vectors @ vectors.T
    projected_sq = np.einsum("ij,ij->i", projected, projected)
    if np.any(projected_sq <= 0.0):
        raise ValueError("Degenerate projected residual norm")
    centered_sq = np.einsum("ij,ij->i", centered, centered)
    eta = 1.0 / float(np.mean(centered_sq / projected_sq))
    return np.sqrt(projected_sq) / np.sqrt(eta) / np.sqrt(float(nc))


def poet_covariance(standardized_residual: object, K: int = 3) -> np.ndarray:
    residual = _as_finite_float64(standardized_residual, ndim=2, name="POET input")
    Y = residual.T.copy()
    p, n = Y.shape
    K = int(K)
    if K < 0 or K >= min(p, n):
        raise ValueError("Invalid POET input")
    Y -= np.mean(Y, axis=1, keepdims=True)
    # The low-rank component uses K principal factors; the diagonal keeps residual risk.
    if K > 0:
        gram = Y.T @ Y
        gram = (gram + gram.T) / 2.0
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        order = np.arange(eigenvalues.size - 1, eigenvalues.size - K - 1, -1)
        F = np.sqrt(float(n)) * eigenvectors[:, order]
        loadings = Y @ F / float(n)
        uhat = Y - loadings @ F.T
        lowrank = loadings @ loadings.T
    else:
        uhat = Y
        lowrank = np.zeros((p, p), dtype=np.float64)
    variance = np.einsum("ij,ij->i", uhat, uhat) / float(n)
    if not np.isfinite(variance).all() or np.any(variance <= 0.0):
        raise ValueError("Invalid POET residual variance")
    covariance = lowrank.copy()
    covariance[np.diag_indices(p)] += variance
    covariance = (covariance + covariance.T) / 2.0
    if not np.isfinite(covariance).all():
        raise ValueError("Nonfinite POET covariance")
    return covariance


def zero_invest_theta(means: object, covariance: object, gamma: object) -> np.ndarray:
    mean_matrix = _as_finite_float64(means, ndim=2, name="theta means")
    sigma = _as_finite_float64(covariance, ndim=2, name="theta covariance")
    scale = _as_finite_float64(gamma, ndim=1, name="theta gamma")
    if (
        sigma.shape != (mean_matrix.shape[1], mean_matrix.shape[1])
        or scale.size != mean_matrix.shape[0]
    ):
        raise ValueError("Invalid theta dimensions")
    try:
        lower = np.linalg.cholesky(sigma)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"POET covariance is not positive definite: {exc}") from exc
    # Project whitened means away from the budget vector, imposing 1'w = 0.
    whitened = np.linalg.solve(lower, mean_matrix.T)
    budget = np.linalg.solve(lower, np.ones(mean_matrix.shape[1], dtype=np.float64))
    denominator = float(budget @ budget)
    coefficient = budget @ whitened / denominator
    projected = whitened - budget[:, None] * coefficient[None, :]
    theta = np.einsum("ij,ij->j", projected, projected) / scale**2
    if not np.isfinite(theta).all() or np.any(theta < 0.0):
        raise ValueError("Invalid theta path")
    return theta


def _r_numeric_gradient(
    function: Callable[[np.ndarray], float], parameters: np.ndarray
) -> np.ndarray:
    gradient = np.empty_like(parameters)
    for index in range(parameters.size):
        plus = parameters.copy()
        minus = parameters.copy()
        plus[index] += 0.001
        minus[index] -= 0.001
        gradient[index] = (function(plus) - function(minus)) / 0.002
    return gradient


def _r_vmmin(
    function: Callable[[np.ndarray], float], initial: np.ndarray, maxit: int = 100
) -> dict[str, object]:
    parameters = np.asarray(initial, dtype=np.float64).copy()
    n = parameters.size
    inverse_hessian = np.eye(n, dtype=np.float64)
    value = float(function(parameters))
    if not np.isfinite(value):
        raise ValueError("Initial AR(1) likelihood is not finite")
    minimum = value
    gradient = _r_numeric_gradient(function, parameters)
    gradient_count = 1
    iteration = 1
    last_reset = gradient_count
    count = 0
    relative_tolerance = np.sqrt(_DOUBLE_EPS)
    while True:
        if last_reset == gradient_count:
            inverse_hessian = np.eye(n, dtype=np.float64)
        old_parameters = parameters.copy()
        old_gradient = gradient.copy()
        direction = -(inverse_hessian @ gradient)
        gradient_projection = float(direction @ gradient)
        if gradient_projection < 0.0:
            step_length = 1.0
            accepted = False
            while True:
                parameters = old_parameters + step_length * direction
                count = int(np.count_nonzero(10.0 + old_parameters == 10.0 + parameters))
                if count < n:
                    value = float(function(parameters))
                    accepted = bool(
                        np.isfinite(value)
                        and value <= minimum + gradient_projection * step_length * 0.0001
                    )
                    if not accepted:
                        step_length *= 0.2
                if count == n or accepted:
                    break
            enough = abs(value - minimum) > relative_tolerance * (abs(minimum) + relative_tolerance)
            if not enough:
                count = n
                minimum = value
            if count < n:
                minimum = value
                gradient = _r_numeric_gradient(function, parameters)
                gradient_count += 1
                iteration += 1
                displacement = step_length * direction
                gradient_delta = gradient - old_gradient
                curvature = float(displacement @ gradient_delta)
                if curvature > 0.0:
                    transformed_delta = inverse_hessian @ gradient_delta
                    multiplier = 1.0 + float(transformed_delta @ gradient_delta) / curvature
                    inverse_hessian += (
                        multiplier * np.outer(displacement, displacement)
                        - np.outer(transformed_delta, displacement)
                        - np.outer(displacement, transformed_delta)
                    ) / curvature
                else:
                    last_reset = gradient_count
            elif last_reset < gradient_count:
                count = 0
                last_reset = gradient_count
        else:
            count = 0
            if last_reset == gradient_count:
                count = n
            else:
                last_reset = gradient_count
        if iteration >= maxit:
            break
        if gradient_count - last_reset > 2 * n:
            last_reset = gradient_count
        if count == n and last_reset == gradient_count:
            break
    return parameters


def ar1_ml_forecast(series: object) -> float:
    x = _as_finite_float64(series, ndim=1, name="AR(1) series")
    n = x.size
    if n < 2:
        raise ValueError("AR(1) series is too short")
    initial_mean = float(np.mean(x))
    residual = x - initial_mean
    mean_scale = 10.0 * np.sqrt(float(residual @ residual) / (n - 1.0)) / np.sqrt(float(n))
    if not np.isfinite(mean_scale) or mean_scale <= 0.0:
        raise ValueError("Degenerate AR(1) initialization scale")
    parameter_scale = np.array([1.0, mean_scale], dtype=np.float64)

    def objective(scaled_parameters: np.ndarray) -> float:
        raw_phi, mean = scaled_parameters * parameter_scale
        phi = float(np.tanh(raw_phi))
        if abs(phi) >= 1.0:
            return float("inf")
        centered = x - mean
        innovations = centered[1:] - phi * centered[:-1]
        sum_squares = (1.0 - phi * phi) * centered[0] ** 2 + float(innovations @ innovations)
        if sum_squares <= 0.0 or not np.isfinite(sum_squares):
            return float("inf")
        return 0.5 * (np.log(sum_squares / n) - np.log1p(-(phi * phi)) / n)

    # Use the R-compatible vmmin port so the AR(1) forecast matches the baseline.
    raw_phi, mean = (
        _r_vmmin(objective, np.array([0.0, initial_mean / mean_scale], dtype=np.float64))
        * parameter_scale
    )
    phi = float(np.tanh(raw_phi))
    return float(mean + phi * (x[-1] - mean))


def build_regression_problem(R: object, S: object, mu: object) -> dict[str, object]:
    returns = _as_finite_float64(R, ndim=2, name="MAXSER-PR inputs")
    signals = _as_finite_float64(S, ndim=2, name="MAXSER-PR inputs")
    synthetic_mean = _as_finite_float64(mu, ndim=1, name="MAXSER-PR inputs")
    TT, NN = returns.shape
    if signals.shape != returns.shape or synthetic_mean.size != NN or TT < 6 or (NN < 2):
        raise ValueError("Invalid MAXSER-PR inputs")
    if np.all(signals - np.mean(signals, axis=1, keepdims=True) == 0.0):
        return {"status": "zero"}
    # Estimate time-varying residual scale, then form the MAXSER-PR regression design.
    raw_e = returns - signals
    gamma_e = raw_e - np.mean(raw_e, axis=0, keepdims=True)
    gamma = np.maximum(gamma_path(gamma_e + synthetic_mean, synthetic_mean), _SQRT_DOUBLE_EPS)
    gamma_next = np.sqrt(max(np.exp(ar1_ml_forecast(np.log(gamma**2))), _SQRT_DOUBLE_EPS))
    standardized = raw_e / gamma[:, None]
    X = (standardized - np.mean(standardized, axis=0, keepdims=True)) * gamma_next + synthetic_mean
    theta = zero_invest_theta(
        np.vstack((signals, synthetic_mean)),
        poet_covariance(standardized, K=3),
        np.concatenate((gamma, np.array([gamma_next]))),
    )
    transformed_theta = theta[:TT] / (1.0 + theta[:TT])
    xi = float(np.mean(transformed_theta))
    if not np.isfinite(xi) or xi >= 1.0:
        raise ValueError("Invalid MAXSER-PR xi")
    if xi <= 1e-14:
        return {"status": "zero"}
    # MAXSER uses a constant response calibrated to the target daily volatility.
    response = TARGET_DAILY_SIGMA / np.sqrt(xi * (1.0 - xi))
    return {"status": "ok", "X": X, "Y": np.full(TT, response, dtype=np.float64)}


import math
import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
ALPHA_GRID: FloatArray = np.arange(11, dtype=np.float64) / 100.0
N_LAMBDA = 100
LAMBDA_MIN_RATIO = 0.01
ALPHA_ZERO_REFERENCE = 0.01
CV_FOLDS = 10
CV_SEED = 123
_BLAS_LIMITER: object | None = None


def _limit_blas_threads() -> None:
    global _BLAS_LIMITER
    if _BLAS_LIMITER is not None:
        return
    try:
        from threadpoolctl import threadpool_limits

        _BLAS_LIMITER = threadpool_limits(limits=1, user_api="blas")
    except ImportError:
        pass


def _finite_matrix(value: ArrayLike, name: str, min_rows: int = 1) -> FloatArray:
    answer = np.asarray(value, dtype=np.float64)
    if answer.ndim != 2 or answer.shape[0] < min_rows or answer.shape[1] < 1:
        raise ValueError(f"{name} must be a two-dimensional numeric matrix")
    if not np.isfinite(answer).all():
        raise ValueError(f"{name} must be finite")
    return answer


def _finite_vector(value: ArrayLike, name: str) -> FloatArray:
    answer = np.asarray(value, dtype=np.float64)
    if answer.ndim == 2 and answer.shape[1] == 1:
        answer = answer[:, 0]
    if answer.ndim != 1 or answer.size < 1 or (not np.isfinite(answer).all()):
        raise ValueError(f"{name} must be a finite numeric vector")
    return answer


def transform_helmert_design(X: ArrayLike) -> FloatArray:
    matrix = _finite_matrix(X, "X")
    n_assets = matrix.shape[1]
    if n_assets < 2:
        raise ValueError("Helmert design needs at least two assets")
    # Helmert coordinates span the zero-sum asset subspace without adding a constraint.
    p = n_assets - 1
    denominator = np.sqrt(
        np.arange(1, p + 1, dtype=np.float64) * np.arange(2, p + 2, dtype=np.float64)
    )
    design = np.empty((matrix.shape[0], p), dtype=np.float64)
    prefix = matrix[:, 0].copy()
    for j in range(p):
        design[:, j] = ((j + 1) * matrix[:, j + 1] - prefix) / denominator[j]
        if j + 1 < p:
            prefix += matrix[:, j + 1]
    return design


def recover_helmert_weights(beta: ArrayLike) -> FloatArray:
    coefficients = np.asarray(beta, dtype=np.float64)
    vector_input = coefficients.ndim == 1
    if vector_input:
        coefficients = coefficients[:, None]
    if (
        coefficients.ndim != 2
        or coefficients.shape[0] < 1
        or coefficients.shape[1] < 1
        or (not np.isfinite(coefficients).all())
    ):
        raise ValueError("beta must be a finite vector or matrix with at least one row")
    # Map coordinate coefficients back to asset weights whose sum is zero.
    p = coefficients.shape[0]
    denominator = np.sqrt(
        np.arange(1, p + 1, dtype=np.float64) * np.arange(2, p + 2, dtype=np.float64)
    )
    scaled = coefficients / denominator[:, None]
    weights = np.zeros((p + 1, coefficients.shape[1]), dtype=np.float64)
    weights[p, :] = p * scaled[p - 1, :]
    suffix = np.zeros(coefficients.shape[1], dtype=np.float64)
    for j in range(p - 1, -1, -1):
        suffix += scaled[j, :]
        weights[j, :] = -suffix
        if j > 0:
            weights[j, :] += j * scaled[j - 1, :]
    return weights[:, 0] if vector_input else weights


def build_lambda_grid(
    X: ArrayLike,
    y: ArrayLike,
    alpha_grid: ArrayLike = ALPHA_GRID,
    n_lambda: int = N_LAMBDA,
    lambda_min_ratio: float = LAMBDA_MIN_RATIO,
    alpha_zero_reference: float = ALPHA_ZERO_REFERENCE,
) -> tuple[FloatArray, ...]:
    matrix = _finite_matrix(X, "X")
    response = _finite_vector(y, "y")
    alphas = _finite_vector(alpha_grid, "alpha_grid")
    if response.size != matrix.shape[0]:
        raise ValueError("X and y row counts differ")
    if not isinstance(n_lambda, (int, np.integer)) or n_lambda < 2:
        raise ValueError("n_lambda must be an integer >= 2")
    if not 0.0 < lambda_min_ratio < 1.0:
        raise ValueError("lambda_min_ratio must lie in (0, 1)")
    if not 0.0 < alpha_zero_reference <= 1.0:
        raise ValueError("alpha_zero_reference must lie in (0, 1]")
    if (alphas < 0).any() or (alphas > 1).any():
        raise ValueError("alpha_grid must lie in [0, 1]")
    gradient = matrix.T @ response / matrix.shape[0]
    spread = float(np.max(gradient) - np.min(gradient))
    centered_norm = float(np.linalg.norm(gradient - np.mean(gradient)))
    paths: list[FloatArray] = []
    for alpha in alphas:
        # alpha=0 reuses the alpha=.01 scale only to define a finite ridge lambda grid.
        path_alpha = alpha_zero_reference if alpha == 0.0 else float(alpha)
        if spread == 0.0 or centered_norm == 0.0:
            paths.append(np.zeros(n_lambda, dtype=np.float64))
            continue
        upper = centered_norm / path_alpha
        lower = spread / (2.0 * path_alpha) * lambda_min_ratio
        path = np.exp(np.linspace(math.log(upper), math.log(lower), n_lambda))
        path[0] = upper
        paths.append(path)
    return tuple(paths)


class _RMersenneTwister:
    _N = 624
    _M = 397
    _MASK32 = 4294967295
    _MATRIX_A = 2567483615
    _UPPER_MASK = 2147483648
    _LOWER_MASK = 2147483647

    def __init__(self, seed: int):
        if not isinstance(seed, (int, np.integer)) or not 0 <= int(seed) <= 2147483647:
            raise ValueError("seed must be an R-compatible nonnegative integer")
        state_seed = int(seed) & self._MASK32
        for _ in range(50):
            state_seed = 69069 * state_seed + 1 & self._MASK32
        raw = np.empty(self._N + 1, dtype=np.uint32)
        for j in range(self._N + 1):
            state_seed = 69069 * state_seed + 1 & self._MASK32
            raw[j] = state_seed
        self._state = raw[1:].copy()
        self._index = self._N

    def _uint32(self) -> int:
        if self._index >= self._N:
            state = self._state
            for kk in range(self._N - self._M):
                y = int(state[kk]) & self._UPPER_MASK | int(state[kk + 1]) & self._LOWER_MASK
                state[kk] = int(state[kk + self._M]) ^ y >> 1 ^ (self._MATRIX_A if y & 1 else 0)
            for kk in range(self._N - self._M, self._N - 1):
                y = int(state[kk]) & self._UPPER_MASK | int(state[kk + 1]) & self._LOWER_MASK
                state[kk] = (
                    int(state[kk + self._M - self._N]) ^ y >> 1 ^ (self._MATRIX_A if y & 1 else 0)
                )
            y = int(state[self._N - 1]) & self._UPPER_MASK | int(state[0]) & self._LOWER_MASK
            state[self._N - 1] = int(state[self._M - 1]) ^ y >> 1 ^ (self._MATRIX_A if y & 1 else 0)
            self._index = 0
        y = int(self._state[self._index])
        self._index += 1
        y ^= y >> 11
        y ^= y << 7 & 2636928640
        y ^= y << 15 & 4022730752
        y ^= y >> 18
        return y & self._MASK32

    def uniform(self) -> float:
        value = self._uint32() * (1.0 / 4294967296.0)
        if value <= 0.0:
            return 0.5 / 4294967295.0
        if 1.0 - value <= 0.0:
            return 1.0 - 0.5 / 4294967295.0
        return value

    def uniform_index(self, n: int) -> int:
        if not isinstance(n, (int, np.integer)) or n < 1:
            raise ValueError("n must be a positive integer")
        bits = int(math.ceil(math.log2(n)))
        mask = (1 << bits) - 1
        while True:
            value = 0
            for _ in range(0, bits + 1, 16):
                value = 65536 * value + int(math.floor(self.uniform() * 65536.0))
            value &= mask
            if value < n:
                return value


def r_sample(n: int, seed: int = CV_SEED) -> IntArray:
    if not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError("n must be a positive integer")
    rng = _RMersenneTwister(seed)
    pool = np.arange(n, dtype=np.int64)
    result = np.empty(n, dtype=np.int64)
    remaining = n
    for i in range(n):
        j = rng.uniform_index(remaining)
        result[i] = pool[j]
        remaining -= 1
        pool[j] = pool[remaining]
    return result


def build_cv_folds(n: int, n_folds: int = CV_FOLDS, seed: int = CV_SEED) -> tuple[IntArray, ...]:
    if not isinstance(n_folds, (int, np.integer)) or n_folds < 2 or n_folds > n // 2:
        raise ValueError("n_folds must lie between 2 and floor(n / 2)")
    permutation = r_sample(n, seed)
    return tuple((permutation[k::n_folds].copy() for k in range(n_folds)))


def solve_ridge_path(Z: ArrayLike, y: ArrayLike, lambdas: ArrayLike) -> FloatArray:
    design = _finite_matrix(Z, "Z", min_rows=2)
    response = _finite_vector(y, "y")
    penalty = _finite_vector(lambdas, "lambdas")
    if response.size != design.shape[0] or (penalty <= 0).any():
        raise ValueError("Invalid ridge path inputs")
    _limit_blas_threads()
    # Solve the no-intercept ridge path
    kernel = design @ design.T / design.shape[0]
    values, vectors = np.linalg.eigh((kernel + kernel.T) / 2.0)
    values = np.maximum(values, 0.0)
    dual = vectors @ ((vectors.T @ response)[:, None] / (values[:, None] + penalty[None, :]))
    beta = design.T @ dual / design.shape[0]
    if not np.isfinite(beta).all():
        raise RuntimeError("nonfinite ridge path")
    return beta


def solve_positive_enet_path(
    Z: ArrayLike, y: ArrayLike, lambdas: ArrayLike, alpha: float, *, max_iter: int = 1000000
) -> FloatArray:
    design = _finite_matrix(Z, "Z", min_rows=2)
    response = _finite_vector(y, "y")
    penalty = _finite_vector(lambdas, "lambdas")
    if response.size != design.shape[0] or not 0.0 < alpha < 1.0:
        raise ValueError("Invalid positive elastic-net inputs")
    if (penalty <= 0).any() or np.any(np.diff(penalty) > 0.0):
        raise ValueError("elastic-net lambdas must be positive and descending")
    from scipy.linalg import cho_factor, cho_solve

    _limit_blas_threads()
    design = np.asfortranarray(design)
    t, p = design.shape
    q = 1.0 - float(alpha)
    active = np.zeros(p, dtype=bool)
    signs = np.zeros(p, dtype=np.float64)
    kernel = np.zeros((t, t), dtype=np.float64)
    signed_sum = np.zeros(t, dtype=np.float64)
    beta = np.empty((p, penalty.size), dtype=np.float64)
    gradient_zero = design.T @ response / t
    eps = np.finfo(np.float64).eps
    gamma_t = t * eps / (1.0 - t * eps)
    gradient_zero_error = gamma_t * (np.abs(design).T @ np.abs(response)) / t + 4.0 * eps * np.abs(
        gradient_zero
    )
    # Active-set updates solve the same no-intercept elastic-net objective as glmnet.
    for path_index, lam in enumerate(penalty):
        if path_index and path_index % 25 == 0:
            active_design = design[:, active]
            kernel = active_design @ active_design.T
        threshold = lam * alpha
        ridge = lam * q
        zero_limit = threshold + gradient_zero_error + 4.0 * abs(np.spacing(threshold))
        if not np.any(active) and np.all(np.abs(gradient_zero) <= zero_limit):
            beta[:, path_index] = 0.0
            continue
        seen: set[tuple[bytes, bytes]] = set()
        for _ in range(max_iter):
            key = (active.tobytes(), signs.tobytes())
            if key in seen:
                raise RuntimeError(f"elastic-net active set cycled at lambda {path_index}")
            seen.add(key)
            if not np.any(active):
                dual_residual = response
            else:
                system = kernel / (t * ridge)
                system.flat[:: t + 1] += 1.0
                right = response + alpha / q * signed_sum
                factor = cho_factor(system, lower=True, overwrite_a=True, check_finite=False)
                dual_residual = cho_solve(factor, right, check_finite=False)
            v = design.T @ dual_residual / t
            new_active = np.abs(v) > threshold
            new_signs = np.where(new_active, np.sign(v), 0.0)
            if np.array_equal(new_active, active) and np.array_equal(new_signs, signs):
                break
            added, dropped = (new_active & ~active, active & ~new_active)
            if np.any(added):
                changed = design[:, added]
                kernel += changed @ changed.T
            if np.any(dropped):
                changed = design[:, dropped]
                kernel -= changed @ changed.T
            active, signs = (new_active, new_signs)
            signed_sum = design[:, active] @ signs[active]
        else:
            raise RuntimeError(f"elastic-net active set exceeded max_iter at lambda {path_index}")
        soft = np.sign(v) * np.maximum(np.abs(v) - threshold, 0.0)
        beta[:, path_index] = soft / ridge
    if not np.isfinite(beta).all():
        raise RuntimeError("nonfinite elastic-net path")
    return beta


def solve_elastic_net_path(
    Z: ArrayLike, y: ArrayLike, lambdas: ArrayLike, alpha: float, *, max_iter: int = 1000000
) -> FloatArray:
    if not np.isfinite(alpha) or not 0.0 <= alpha < 1.0:
        raise ValueError("alpha must lie in [0, 1)")
    if alpha == 0.0:
        return solve_ridge_path(Z, y, lambdas)
    return solve_positive_enet_path(Z, y, lambdas, float(alpha), max_iter=max_iter)


def fit_elastic_net_cv(
    X: ArrayLike,
    y: ArrayLike,
    *,
    alpha_grid: ArrayLike = ALPHA_GRID,
    n_lambda: int = N_LAMBDA,
    lambda_min_ratio: float = LAMBDA_MIN_RATIO,
    alpha_zero_reference: float = ALPHA_ZERO_REFERENCE,
    n_folds: int = CV_FOLDS,
    seed: int = CV_SEED,
    max_iter: int = 1000000,
) -> FloatArray:
    matrix = _finite_matrix(X, "X", min_rows=4)
    response = _finite_vector(y, "y")
    alphas = _finite_vector(alpha_grid, "alpha_grid")
    if response.size != matrix.shape[0] or matrix.shape[1] < 2:
        raise ValueError("Invalid regression inputs")
    if (alphas < 0.0).any() or (alphas >= 1.0).any() or np.any(np.diff(alphas) < 0.0):
        raise ValueError("alpha_grid must be ascending within [0, 1)")
    grids = build_lambda_grid(
        matrix, response, alphas, n_lambda, lambda_min_ratio, alpha_zero_reference
    )
    if any(((grid <= 0.0).any() for grid in grids)):
        raise ValueError("degenerate lambda path")
    folds = build_cv_folds(matrix.shape[0], n_folds, seed)
    fold_sr2 = np.full((alphas.size, n_lambda, n_folds), -np.inf, dtype=np.float64)
    all_rows = np.arange(matrix.shape[0], dtype=np.int64)
    for fold_index, omit in enumerate(folds):
        keep = np.ones(matrix.shape[0], dtype=bool)
        keep[omit] = False
        train = all_rows[keep]
        train_design = transform_helmert_design(matrix[train])
        for alpha_index, alpha in enumerate(alphas):
            beta = solve_elastic_net_path(
                train_design, response[train], grids[alpha_index], float(alpha), max_iter=max_iter
            )
            # Score every candidate by held-out squared Sharpe ratio.
            heldout = matrix[omit] @ recover_helmert_weights(beta)
            means = np.mean(heldout, axis=0)
            risks = np.std(heldout, axis=0, ddof=1)
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                score = (means / risks) ** 2
            score[~np.isfinite(score)] = -np.inf
            fold_sr2[alpha_index, :, fold_index] = score
    mean_sr2 = np.full((alphas.size, n_lambda), -np.inf, dtype=np.float64)
    valid = np.all(np.isfinite(fold_sr2), axis=2)
    for alpha_index in range(alphas.size):
        selected = valid[alpha_index]
        if np.any(selected):
            mean_sr2[alpha_index, selected] = np.mean(fold_sr2[alpha_index, selected], axis=1)
        if not np.isfinite(mean_sr2[alpha_index]).any():
            raise RuntimeError(f"no finite CV candidate for alpha={alphas[alpha_index]}")
    best_lambda = np.argmax(mean_sr2, axis=1)
    alpha_index = int(np.argmax(mean_sr2[np.arange(alphas.size), best_lambda]))
    lambda_index = int(best_lambda[alpha_index])
    beta = solve_elastic_net_path(
        transform_helmert_design(matrix),
        response,
        np.asarray([grids[alpha_index][lambda_index]], dtype=np.float64),
        float(alphas[alpha_index]),
        max_iter=max_iter,
    )[:, 0]
    weights = recover_helmert_weights(beta)
    budget_limit = 1e-10 + 1e-10 * np.sum(np.abs(weights))
    if not np.isfinite(weights).all() or abs(float(np.sum(weights))) > budget_limit:
        raise RuntimeError("invalid final weights")
    return weights


import numpy as np
import pandas as pd
