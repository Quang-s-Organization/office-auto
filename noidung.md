# Deep Learning Approaches for Biomedical Image Segmentation

**Nguyen Thi Lan**<sup>1</sup>, **Tran Minh Duc**<sup>2</sup>, **Le Hoang Anh**<sup>3</sup>, **Pham Quoc Bao**<sup>4</sup>

<sup>1</sup>Department of Computer Science, Hanoi University of Science and Technology, Hanoi, Vietnam

<sup>2</sup>Faculty of Biomedical Engineering, Vietnam National University, Ho Chi Minh City, Vietnam

<sup>3</sup>Institute of Artificial Intelligence, Vingroup Big Data Institute, Hanoi, Vietnam

<sup>4</sup>Department of Radiology, Bach Mai Hospital, Hanoi, Vietnam

---

*This chapter is dedicated to all healthcare workers who tirelessly serve patients and inspire the development of life-saving technologies.*

> *"The goal of computer vision in medicine is not to replace the physician, but to give them a superpower." — Anonymous*

---

**Abstract** Accurate segmentation of anatomical structures in medical images is a fundamental step in clinical diagnosis, treatment planning, and disease monitoring. Traditional segmentation methods often fall short when confronted with the high variability of biological tissue and imaging noise. This chapter presents a comprehensive review of deep learning architectures applied to biomedical image segmentation, with a particular focus on convolutional neural networks (CNNs) and transformer-based models. We survey benchmark datasets, evaluation metrics, and training strategies, and discuss both the opportunities and limitations of current approaches. Experimental results on three public datasets demonstrate that hybrid architectures combining local feature extraction with global context modelling consistently outperform single-paradigm methods.

**Keywords** Deep Learning, Image Segmentation, Convolutional Neural Networks, Vision Transformers, Medical Imaging, U-Net

---

# Introduction

The automated analysis of biomedical images has become an indispensable component of modern healthcare. With the growing volume of radiology scans, histopathology slides, and endoscopic images generated each year, manual annotation by clinicians is no longer scalable. Deep learning has emerged as the dominant paradigm for tackling this challenge, offering end-to-end solutions that can learn rich hierarchical representations directly from raw pixel data.

Image segmentation — the task of assigning a semantic label to every pixel in an image — is arguably the most information-dense form of visual understanding. In the biomedical domain this translates to delineating tumours, organs, lesions, and cellular structures with sub-millimetre precision. Errors in segmentation can propagate to downstream tasks such as volumetric measurement, radiotherapy planning, and computer-aided diagnosis, making accuracy paramount.

This chapter is organised as follows. → Section 2 introduces the foundational concepts of encoder–decoder networks. → Section 3 discusses attention mechanisms and transformer adaptations. → Section 4 covers training strategies and data augmentation. → Section 5 presents experimental comparisons, and → Section 6 concludes with open research directions.

# Encoder–Decoder Architectures

## The U-Net Family

The U-Net architecture (Ronneberger et al. 2015) revolutionised biomedical segmentation by introducing symmetric skip connections between the contracting and expansive paths of a fully convolutional network. These skip connections preserve fine-grained spatial information that is otherwise lost during repeated pooling operations, enabling precise localisation even when the model is trained on a limited number of annotated images.

Several extensions of U-Net have been proposed to address its shortcomings:

- **U-Net++**: Introduces nested, dense skip pathways that re-design skip connections as a series of nested dense blocks, reducing the semantic gap between encoder and decoder feature maps.
- **Attention U-Net**: Adds attention gates at skip connections to suppress irrelevant activations and focus on salient regions, particularly beneficial for multi-class segmentation.
- **3D U-Net**: Extends the architecture to volumetric data by replacing 2D convolutions with 3D convolutions, enabling direct processing of CT and MRI volumes.
- **Residual U-Net**: Replaces standard convolutional blocks with residual units to facilitate gradient flow during training of deeper networks.

## Fully Convolutional Networks

Prior to U-Net, fully convolutional networks (FCNs) established the groundwork for dense prediction by discarding fully connected layers and replacing them with convolutional layers, thereby allowing the network to accept inputs of arbitrary spatial resolution. FCN-based models remain competitive on natural image benchmarks, though they are generally outperformed by encoder–decoder designs on medical data where precise boundary delineation is critical.

**Important** Skip connections are essential in biomedical segmentation. Without them, upsampling paths recover only coarse spatial structure. Always verify that skip connections are correctly wired when implementing custom architectures.

## Loss Functions

The choice of loss function has a substantial impact on segmentation quality, especially in the presence of class imbalance — a common scenario in medical imaging where foreground regions (e.g. small lesions) occupy only a fraction of the image area. Commonly used loss functions include:

1. **Cross-Entropy Loss**: The standard pixel-wise classification loss, sensitive to class imbalance.
2. **Dice Loss**: Directly optimises the Dice Similarity Coefficient (DSC), robust to imbalance but prone to instability at the start of training.
3. **Tversky Loss**: A generalisation of Dice loss that introduces weighting parameters α and β to penalise false positives and false negatives asymmetrically.
4. **Boundary Loss**: Penalises predictions that deviate from the true contour, improving edge accuracy.

In practice, a combination of cross-entropy and Dice loss is widely adopted:

```python
def combined_loss(pred, target, alpha=0.5):
    ce = F.cross_entropy(pred, target)
    dice = dice_loss(pred, target)
    return alpha * ce + (1 - alpha) * dice
```

# Attention Mechanisms and Transformers

## Self-Attention in Segmentation

The introduction of the Transformer architecture (Vaswani et al. 2017) to vision tasks brought a paradigm shift: instead of relying solely on local receptive fields, self-attention allows every position in the feature map to attend to every other position, capturing long-range dependencies that are difficult to model with convolutions alone.

For biomedical segmentation, this global context is particularly valuable. In organ segmentation, for instance, the position and shape of one organ constrain the plausible location and extent of adjacent organs. A self-attention layer with a receptive field spanning the entire image can implicitly encode such anatomical priors without requiring explicit shape models.

The self-attention operation is defined as:

$$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^T}{\sqrt{d_k}}\right)V \tag{1}$$

where Q, K, and V denote the query, key, and value matrices, respectively, and d_k is the dimensionality of the key vectors. The scaling factor √d_k prevents the dot products from growing large in magnitude and pushing the softmax into regions of extremely small gradients.

## Hybrid CNN–Transformer Models

Pure transformer models require large amounts of training data to outperform CNNs, because they lack the inductive biases (translation equivariance, local connectivity) that are built into convolutional operators. Hybrid models address this by combining a CNN backbone for local feature extraction with a transformer module for global context aggregation.

**TransUNet** (Chen et al. 2021) exemplifies this approach: image patches extracted from an intermediate CNN feature map are serialised into a sequence and fed to a standard ViT encoder. The enriched sequence is then reshaped and passed through a U-Net-style decoder. This design achieves state-of-the-art results on multi-organ segmentation benchmarks while remaining trainable with datasets of moderate size (→ Table 1).

**Definition** A *vision transformer* (ViT) is a neural network architecture that applies the self-attention mechanism of the original Transformer model to non-overlapping patches of an input image, treating each patch as a token analogous to a word in natural language processing.

# Training Strategies and Data Augmentation

## Transfer Learning

Training deep segmentation networks from scratch on small medical datasets typically leads to overfitting. Transfer learning from ImageNet-pretrained weights provides a strong initialisation for the encoder, reducing the amount of annotated data needed to achieve clinically acceptable performance. When ImageNet weights are used, it is important to fine-tune with a lower learning rate (e.g. 1 × 10⁻⁴) in the early layers and a higher rate in the later layers to preserve low-level texture features while adapting high-level semantic representations.

## Data Augmentation

Medical imaging datasets are expensive to annotate and often contain fewer than a few hundred labelled cases. Aggressive data augmentation is therefore essential to improve generalisation. Effective augmentation strategies include:

- Random horizontal and vertical flipping
- Rotation by arbitrary angles (–30° to +30°)
- Elastic deformations to simulate tissue variability
- Random brightness and contrast adjustments
- Gaussian noise and blur
- Mixup and CutMix for label smoothing

**Warning** Do not apply augmentations that alter the semantic content of the label. For instance, colour jitter is appropriate for RGB fundus images but must be applied cautiously to greyscale CT images where Hounsfield unit values carry diagnostic meaning.

## Self-Supervised Pre-training

When even unlabelled data is scarce, self-supervised learning offers an alternative to ImageNet transfer. Contrastive methods such as SimCLR and MoCo learn representations by pulling augmented views of the same image together in latent space while pushing different images apart. Models pre-trained with these objectives on in-domain unlabelled medical images have been shown to match or exceed the performance of ImageNet-pretrained models when fine-tuned with small labelled sets (Aaron 2022).

# Experimental Evaluation

## Datasets and Metrics

Experiments were conducted on three publicly available datasets:

- **ACDC** (Automated Cardiac Diagnosis Challenge): 100 cardiac MRI studies with manually delineated right ventricle, myocardium, and left ventricle.
- **Synapse Multi-Organ**: 30 abdominal CT scans with 8 organ classes annotated by radiologists.
- **GlaS** (Gland Segmentation): 165 H&E stained colon histology images with gland instance masks.

The primary evaluation metric is the Dice Similarity Coefficient:

$$\text{DSC}(P, G) = \frac{2|P \cap G|}{|P| + |G|} \tag{2}$$

where P and G denote the predicted and ground-truth binary masks, respectively. A DSC of 1.0 indicates perfect overlap; a DSC of 0.0 indicates no overlap. Additional metrics include the 95th-percentile Hausdorff Distance (HD95) and mean Intersection over Union (mIoU).

## Results

**Table 1** Comparison of segmentation methods on the Synapse multi-organ benchmark (mean DSC ± std, %)

| Method | Aorta | Gallbladder | Spleen | Left Kidney | Mean DSC |
|---|---|---|---|---|---|
| FCN (baseline) | 76.3 ± 3.1 | 43.2 ± 8.4 | 84.1 ± 2.9 | 77.6 ± 4.2 | 70.3 |
| U-Net | 87.7 ± 2.3 | 63.1 ± 7.1 | 94.1 ± 1.4 | 81.5 ± 3.8 | 76.9 |
| Attention U-Net | 89.1 ± 1.9 | 66.3 ± 6.8 | 94.7 ± 1.2 | 84.2 ± 3.1 | 79.0 |
| TransUNet | 87.2 ± 2.7 | 63.1 ± 7.8 | 94.1 ± 1.6 | 77.0 ± 4.5 | 77.5 |
| **Ours (Hybrid)** | **90.4 ± 1.5** | **68.7 ± 5.9** | **95.3 ± 0.9** | **86.1 ± 2.6** | **81.1** |

<sup>a</sup>All methods trained with identical augmentation pipelines and evaluated on the same 18 test cases.

The proposed hybrid model achieves the highest mean DSC across all reported organ classes (→ Table 1). Notably, gallbladder segmentation remains challenging for all methods due to its variable shape and size, as well as frequent absence in post-cholecystectomy patients. The improvement over Attention U-Net is statistically significant (p < 0.05, paired Wilcoxon signed-rank test).

**Example** To reproduce our best result, initialise the encoder with ImageNet weights, train for 200 epochs with a cosine annealing learning rate schedule (initial lr = 3 × 10⁻⁴), and apply the combined Dice + cross-entropy loss with α = 0.4. Batch size of 16 on a single NVIDIA A100 GPU yields convergence within approximately 6 hours.

# Conclusion and Future Directions

This chapter has reviewed the landscape of deep learning methods for biomedical image segmentation, tracing the evolution from fully convolutional networks through encoder–decoder architectures to hybrid CNN–transformer models. Experimental results confirm that combining local feature extraction with global context modelling offers a reliable path to improved segmentation accuracy across diverse imaging modalities.

Several open challenges remain. First, the reliance on large quantities of pixel-level annotations is a fundamental bottleneck; semi-supervised and weakly supervised methods that leverage annotation-efficient labels (e.g. bounding boxes, scribbles) are an active and promising research direction. Second, domain shift between scanners and imaging protocols limits the deployment of models trained in one clinical centre to another; federated learning and domain adaptation techniques offer partial solutions but have yet to achieve the robustness needed for widespread clinical adoption. Third, the interpretability of deep segmentation models — understanding *why* a network assigns a particular label to a pixel — remains an open question with direct implications for regulatory approval and clinician trust.

Future work will explore foundation models pre-trained on large-scale multimodal medical corpora, prompt-guided segmentation akin to the Segment Anything Model (SAM), and uncertainty quantification methods that provide calibrated confidence estimates alongside predictions.

---

## Appendix

### Appendix 1: Hyperparameter Search Protocol

All hyperparameters were selected via a random search over 50 configurations on the validation split. The search space included learning rate ∈ {1e-3, 3e-4, 1e-4}, weight decay ∈ {1e-4, 1e-5}, and batch size ∈ {8, 16, 32}. Early stopping with patience of 20 epochs was applied to prevent overfitting.

### Appendix 2: Implementation Details

All models were implemented in PyTorch 2.1 and trained on a cluster of 4 × NVIDIA A100 (80 GB) GPUs. Mixed-precision training (FP16) was used throughout to reduce memory consumption. Code and pre-trained weights are available at `https://github.com/example/biomed-seg`.

---

## Acknowledgments

The authors thank the clinical teams at Bach Mai Hospital for their invaluable assistance with data annotation, and the Vingroup Big Data Institute for providing high-performance computing resources. This research was supported by the Vietnam National Foundation for Science and Technology Development (NAFOSTED) under grant number 102.05-2023.15.

---

## Competing Interests

Nguyen Thi Lan has received a research grant from MedAI Solutions Ltd. (grant number MAS-2024-07). The remaining authors declare no competing interests relevant to the content of this chapter.

---

## Ethics Approval

All imaging data used in this study were collected in line with the principles of the Declaration of Helsinki. Ethical approval was granted by the Institutional Review Board of Bach Mai Hospital (Approval No. IRB-BM-2023-112, dated 14 March 2023). Written informed consent was obtained from all participants prior to data collection.

---

# References

Aaron M (2022) Self-supervised representation learning for medical image analysis. J Med Imaging 9(3):034501. https://doi.org/10.1117/1.JMI.9.3.034501

Bahdanau D, Cho K, Bengio Y (2015) Neural machine translation by jointly learning to align and translate. In: Proceedings of ICLR 2015, San Diego

Chen J, Lu Y, Yu Q et al (2021) TransUNet: transformers make strong encoders for medical image segmentation. Preprint at https://arxiv.org/abs/2102.04306

Dosovitskiy A, Beyer L, Kolesnikov A et al (2021) An image is worth 16×16 words: transformers for image recognition at scale. In: Proceedings of ICLR 2021

He K, Zhang X, Ren S, Sun J (2016) Deep residual learning for image recognition. In: Proceedings of CVPR 2016, Las Vegas, pp 770–778

Isensee F, Jaeger PF, Kohl SAA et al (2021) nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nat Methods 18:203–211. https://doi.org/10.1038/s41592-020-01008-z

Litjens G, Kooi T, Bejnordi BE et al (2017) A survey on deep learning in medical image analysis. Med Image Anal 42:60–88. https://doi.org/10.1016/j.media.2017.07.005

Milletari F, Navab N, Ahmadi S-A (2016) V-Net: fully convolutional neural networks for volumetric medical image segmentation. In: Proceedings of 3DV 2016, Stanford, pp 565–571

Ronneberger O, Fischer P, Brox T (2015) U-Net: convolutional networks for biomedical image segmentation. In: Navab N et al (eds) Medical image computing and computer-assisted intervention – MICCAI 2015. Lecture notes in computer science, vol 9351. Springer, Cham, pp 234–241

Simonyan K, Zisserman A (2015) Very deep convolutional networks for large-scale image recognition. In: Proceedings of ICLR 2015, San Diego

Vaswani A, Shazeer N, Parmar N et al (2017) Attention is all you need. In: Advances in neural information processing systems, vol 30. Curran Associates, Red Hook, pp 5998–6008

Wang W, Chen C, Ding M et al (2022) TransBTS: multimodal brain tumor segmentation using transformer. In: de Bruijne M et al (eds) Medical image computing and computer-assisted intervention – MICCAI 2021. Lecture notes in computer science, vol 12901. Springer, Cham, pp 109–119

Zhou Z, Rahman Siddiquee MM, Tajbakhsh N, Liang J (2019) UNet++: a nested U-Net architecture for medical image segmentation. In: Shen D et al (eds) Deep learning in medical image analysis and multimodal learning for clinical decision support. Lecture notes in computer science, vol 11045. Springer, Cham, pp 3–11